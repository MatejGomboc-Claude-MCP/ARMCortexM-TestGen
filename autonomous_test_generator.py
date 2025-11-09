#!/usr/bin/env python3
"""
Autonomous Test Generator for GitHub Actions

Runs unattended in GitHub Actions, uses Claude API to generate and validate tests.
Perfect for overnight runs - submit before bed, review PR in the morning!

Usage (in GitHub Actions):
    python autonomous_test_generator.py --functions setBit clearBit
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
import logging

try:
    import anthropic
except ImportError:
    print("Installing anthropic package...")
    subprocess.run([sys.executable, "-m", "pip", "install", "anthropic"], check=True)
    import anthropic

from anthropic import RateLimitError

# Import our function parser
from function_parser import FunctionParser, validate_function_exists, FunctionSignature


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('testgen.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Standardized error prefix for consistent error checking
ERROR_PREFIX = "ERROR: "


class AutonomousTestGenerator:
    """Single Claude agent that generates, compiles, and validates tests autonomously"""
    
    def __init__(self, repo_path: Path, api_key: str, max_cost: float = 50.0, module: str = "bit_utils"):
        self.repo_path = Path(repo_path)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.max_cost = max_cost
        self.module = module
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        
        # Cost per 1M tokens
        self.input_cost_per_million = 3.0
        self.output_cost_per_million = 15.0
        
        logger.info(f"Initialized generator for module: {module}")
        logger.info(f"Repository path: {repo_path}")
        logger.info(f"Max cost: ${max_cost}")
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate API cost"""
        input_cost = (input_tokens / 1_000_000) * self.input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * self.output_cost_per_million
        return input_cost + output_cost
    
    def call_claude(self, prompt: str, max_tokens: int = 8000) -> str:
        """Make API call to Claude with rate limit handling"""
        logger.info("Calling Claude API...")
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=max_tokens,
                    temperature=0.2,  # Low temp for consistency
                    messages=[{"role": "user", "content": prompt}]
                )
                
                # Track usage
                self.total_input_tokens += response.usage.input_tokens
                self.total_output_tokens += response.usage.output_tokens
                
                cost = self.calculate_cost(response.usage.input_tokens, response.usage.output_tokens)
                self.total_cost += cost
                
                logger.info(f"   Input tokens: {response.usage.input_tokens:,}")
                logger.info(f"   Output tokens: {response.usage.output_tokens:,}")
                logger.info(f"   Call cost: ${cost:.4f}")
                logger.info(f"   Total cost so far: ${self.total_cost:.4f}")
                
                if self.total_cost > self.max_cost:
                    raise RuntimeError(
                        f"Cost limit ${self.max_cost} exceeded!\n"
                        f"   Spent: ${self.total_cost:.2f}\n"
                        f"   Suggestion: Increase --max-cost to continue"
                    )
                
                return response.content[0].text
                
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4, 8, 16 seconds
                    logger.warning(f"⏳ Rate limited, waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error("❌ Rate limit exceeded after all retries")
                    raise
    
    def read_file(self, relative_path: str) -> str:
        """Read file from repo"""
        file_path = self.repo_path / relative_path
        if not file_path.exists():
            error_msg = f"File not found: {relative_path}"
            logger.error(error_msg)
            return f"{ERROR_PREFIX}{error_msg}"
        
        try:
            content = file_path.read_text()
            logger.debug(f"Read {relative_path} ({len(content)} bytes)")
            return content
        except Exception as e:
            error_msg = f"Error reading {relative_path}: {e}"
            logger.error(error_msg)
            return f"{ERROR_PREFIX}{error_msg}"
    
    def write_file(self, relative_path: str, content: str) -> bool:
        """Write file to repo"""
        file_path = self.repo_path / relative_path
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            logger.info(f"Wrote {relative_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing {relative_path}: {e}")
            return False
    
    def get_header_path(self) -> Path:
        """Get path to the header file for current module"""
        # Bug #16 fix: Remove useless if statement and add validation
        header_path = self.repo_path / f"{self.module}.hpp"
        
        if not header_path.exists():
            logger.error(f"Header file not found: {header_path}")
            logger.info(f"Expected: {header_path}")
            logger.info(f"Module: {self.module}")
            raise FileNotFoundError(f"Header file not found: {header_path}")
        
        return header_path
    
    def get_test_dir(self) -> Path:
        """Get path to test directory for current module"""
        # Bug #17 fix: Create directory if it doesn't exist
        test_dir = self.repo_path / "tests" / self.module.replace("/", "_")
        
        if not test_dir.exists():
            logger.warning(f"Test directory does not exist: {test_dir}")
            logger.info(f"Creating test directory...")
            test_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"✓ Created test directory: {test_dir}")
        
        return test_dir
    
    def validate_function(self, function_name: str) -> Optional[FunctionSignature]:
        """Validate that function exists and get its signature"""
        header_path = self.get_header_path()
        
        logger.info(f"Validating function '{function_name}' in {header_path.name}...")
        signature = validate_function_exists(header_path, function_name)
        
        if signature is None:
            logger.error(f"Function '{function_name}' not found in {header_path.name}")
            return None
        
        logger.info(f"✓ Found function: {signature.name}")
        logger.info(f"  Return type: {signature.return_type}")
        logger.info(f"  Parameters: {signature.parameters}")
        logger.info(f"  Modifies reference: {signature.modifies_reference}")
        logger.info(f"  Pattern file: {signature.pattern_file}")
        logger.info(f"  Test type: {signature.test_type}")
        
        return signature
    
    def compile_and_test(self, test_name: str, optimization: str) -> Dict[str, Any]:
        """Compile and run tests for a specific optimization level"""
        preset = f"m0-gcc-{optimization.lower()}"
        
        logger.info(f"Compiling {optimization}...")
        
        # Configure
        result = subprocess.run(
            ["cmake", "--preset", preset],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            logger.error(f"Configure failed: {result.stderr[:200]}")
            return {
                "success": False,
                "stage": "configure",
                "output": result.stderr
            }
        
        # Build
        result = subprocess.run(
            ["cmake", "--build", "--preset", preset, "--target", test_name],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=180
        )
        if result.returncode != 0:
            logger.error(f"Build failed: {result.stderr[:200]}")
            return {
                "success": False,
                "stage": "build",
                "output": result.stderr
            }
        
        # Test
        result = subprocess.run(
            ["ctest", "--preset", preset, "-R", test_name, "-V"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            logger.info(f"✓ {optimization} tests passed")
        else:
            logger.warning(f"✗ {optimization} tests failed")
        
        return {
            "success": result.returncode == 0,
            "stage": "test",
            "output": result.stdout + "\n" + result.stderr
        }
    
    def read_assembly(self, test_name: str, optimization: str) -> str:
        """Read generated assembly file"""
        preset = f"m0-gcc-{optimization.lower()}"
        # Dynamic path based on module
        module_dir = self.module.replace("/", "_")
        asm_path = self.repo_path / "build" / preset / "tests" / module_dir / f"{test_name}.asm"
        
        if not asm_path.exists():
            error_msg = f"Assembly file not found: {asm_path}"
            logger.warning(error_msg)
            return f"{ERROR_PREFIX}{error_msg}"
        
        return asm_path.read_text()
    
    def generate_test(self, function_name: str) -> bool:
        """Generate and validate tests for a single function"""
        
        logger.info("=" * 70)
        logger.info(f"GENERATING TESTS FOR {function_name}()")
        logger.info("=" * 70)
        
        # Validate function exists and get signature
        signature = self.validate_function(function_name)
        if signature is None:
            return False
        
        # Read context - use appropriate pattern based on function signature
        logger.info("Reading existing patterns...")
        test_dir = self.get_test_dir()
        pattern_file = test_dir / signature.pattern_file
        
        if not pattern_file.exists():
            logger.error(f"Pattern file not found: {pattern_file}")
            logger.info("Available patterns:")
            for p in test_dir.glob("test_*_runtime.cpp"):
                logger.info(f"  - {p.name}")
            return False
        
        existing_test = pattern_file.read_text()
        logger.info(f"✓ Read pattern ({len(existing_test)} bytes): {pattern_file.name}")
        
        header = self.read_file(self.get_header_path().name)
        if header.startswith(ERROR_PREFIX):
            return False
        logger.info(f"✓ Read header file ({len(header)} bytes)")
        
        # Generate initial test with signature-aware prompt
        logger.info(f"Generating test code for {function_name}()...")
        
        # Build signature-aware instructions
        if signature.test_type == "void-modifying":
            signature_notes = f"""
IMPORTANT NOTES ABOUT {function_name}():
- This function MODIFIES a reference parameter: {signature.parameters[0]}
- Assembly will include MEMORY OPERATIONS (ldr/str instructions)
- The value is loaded, modified, and stored back
"""
        elif signature.test_type == "bool-returning":
            signature_notes = f"""
IMPORTANT NOTES ABOUT {function_name}():
- This function RETURNS a bool value
- Assembly will use comparison and conditional instructions
- No memory writes, only reads and comparisons
"""
        else:
            signature_notes = f"""
IMPORTANT NOTES ABOUT {function_name}():
- This function returns: {signature.return_type}
- Parameters: {', '.join(signature.parameters)}
"""
        
        prompt = f"""You are an expert in ARM Cortex-M assembly and C++ embedded systems testing.

TASK: Generate test_{function_name.lower()}_runtime.cpp following the EXACT pattern.

FUNCTION SIGNATURE:
```cpp
{signature.return_type} {signature.name}({', '.join(signature.parameters)})
```

{signature_notes}

HEADER FILE ({self.get_header_path().name}):
```cpp
{header}
```

PATTERN TO FOLLOW ({signature.pattern_file}):
```cpp
{existing_test}
```

REQUIREMENTS:
1. Test all integer types: uint8_t, uint16_t, uint32_t, uint64_t, int8_t, int16_t, int32_t, int64_t
2. For each type, test bit positions: 0, middle bit, MSB
3. Include CHECK directives for DEBUG, MINSIZE, MAXSPEED optimizations
4. Use extern "C" [[gnu::naked]] for all test functions
5. For signed types checking MSB: bit 7 of int8_t and bit 15 of int16_t become bit 31 after sign extension
6. MAXSPEED optimization adds NOP padding for alignment
7. Each function ends with CHECK-EMPTY:

OUTPUT: The complete C++ test file only. No explanations, no markdown, just the raw C++ code."""

        test_code = self.call_claude(prompt)
        
        # Write test file
        test_filename = f"test_{function_name.lower()}_runtime.cpp"
        test_path = test_dir / test_filename
        test_name = f"test_{function_name.lower()}_runtime"
        
        logger.info(f"Writing {test_path.relative_to(self.repo_path)}...")
        if not self.write_file(str(test_path.relative_to(self.repo_path)), test_code):
            return False
        
        # Update CMakeLists.txt
        cmake_path = test_dir / "CMakeLists.txt"
        cmake_content = self.read_file(str(cmake_path.relative_to(self.repo_path)))
        
        # Bug #12 fix: Validate CMakeLists.txt read before using it
        if cmake_content.startswith(ERROR_PREFIX):
            logger.error(f"Cannot update CMakeLists.txt: {cmake_content}")
            return False
        
        # Check if test already exists in CMakeLists.txt
        test_declaration = f"add_asm_test({test_name})"
        if test_declaration not in cmake_content:
            # Add at the end, preserving formatting
            if not cmake_content.endswith('\n'):
                cmake_content += '\n'
            cmake_content += f"{test_declaration}\n"
            self.write_file(str(cmake_path.relative_to(self.repo_path)), cmake_content)
            logger.info("✓ Updated CMakeLists.txt")
        
        # Try to compile and test (with retries)
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            logger.info("─" * 70)
            logger.info(f"ATTEMPT {attempt}/{max_attempts}")
            logger.info("─" * 70)
            
            all_passed = True
            failed_optimizations = []
            
            for optimization in ["Debug", "MinSize", "MaxSpeed"]:
                result = self.compile_and_test(test_name, optimization)
                
                if not result["success"]:
                    all_passed = False
                    failed_optimizations.append((optimization, result))
            
            if all_passed:
                logger.info(f"🎉 SUCCESS! All tests pass for {function_name}()")
                return True
            
            if attempt < max_attempts:
                logger.info("Fixing failures...")
                
                # Collect assembly for failed optimizations
                assemblies = {}
                for opt, result in failed_optimizations:
                    if result["stage"] == "test":  # Only if we got to testing
                        asm = self.read_assembly(test_name, opt)
                        if not asm.startswith(ERROR_PREFIX):
                            assemblies[opt] = asm
                
                # Bug #13 fix: Better error recovery strategy
                if not assemblies:
                    logger.warning("No assembly available - failures at build/configure stage")
                    logger.warning("Cannot fix CHECK directives without assembly")
                    logger.warning("Check compilation errors above")
                    # Show some error details
                    for opt, result in failed_optimizations:
                        logger.error(f"{opt} failed at {result['stage']}: {result['output'][:300]}")
                    break  # Give up, not worth retrying
                
                # Ask Claude to fix
                fix_prompt = f"""The test file has CHECK directive mismatches. Fix them.

CURRENT TEST FILE:
```cpp
{test_code}
```

ACTUAL ASSEMBLY OUTPUTS:

"""
                for opt, asm in assemblies.items():
                    fix_prompt += f"\n{opt}:\n```\n{asm}\n```\n"
                
                fix_prompt += """
REQUIREMENTS:
1. Update CHECK directives to match actual assembly
2. Keep exact same structure and test functions
3. Only change CHECK-NEXT: lines
4. Remember: MAXSPEED adds NOP padding
5. Keep CHECK-EMPTY: at end of functions

OUTPUT: The complete corrected C++ test file only. No explanations, just the code."""

                test_code = self.call_claude(fix_prompt, max_tokens=12000)
                
                logger.info("Writing corrected version...")
                self.write_file(str(test_path.relative_to(self.repo_path)), test_code)
        
        logger.error(f"FAILED: Could not get tests passing after {max_attempts} attempts")
        return False
    
    def run(self, functions: List[str]) -> Dict[str, Any]:
        """Run autonomous test generation for multiple functions"""
        
        logger.info("=" * 70)
        logger.info("🤖 AUTONOMOUS TEST GENERATOR")
        logger.info("=" * 70)
        logger.info(f"Functions to test: {', '.join(functions)}")
        logger.info(f"Module: {self.module}")
        logger.info(f"Max cost: ${self.max_cost}")
        logger.info("=" * 70)
        
        start_time = time.time()
        results = {}
        
        for func in functions:
            try:
                success = self.generate_test(func)
                results[func] = {
                    "success": success,
                    "error": None
                }
            except Exception as e:
                logger.exception(f"ERROR processing {func}")
                results[func] = {
                    "success": False,
                    "error": str(e)
                }
                break
        
        elapsed = time.time() - start_time
        
        # Print summary
        logger.info("=" * 70)
        logger.info("📊 FINAL SUMMARY")
        logger.info("=" * 70)
        
        for func, result in results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            logger.info(f"{status} - {func}()")
            if result["error"]:
                logger.info(f"       Error: {result['error']}")
        
        logger.info(f"\n⏱️  Time: {elapsed/60:.1f} minutes")
        logger.info(f"💰 Cost: ${self.total_cost:.2f}")
        logger.info(f"🎟️  Tokens: {self.total_input_tokens:,} in, {self.total_output_tokens:,} out")
        logger.info("=" * 70)
        
        return {
            "results": results,
            "total_cost": self.total_cost,
            "elapsed_time": elapsed,
            "all_passed": all(r["success"] for r in results.values())
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Autonomous test generator for ARMCortexM-CppLib"
    )
    parser.add_argument(
        "--functions",
        nargs="+",
        required=True,
        help="Function names to generate tests for (e.g., setBit clearBit)"
    )
    parser.add_argument(
        "--repo-path",
        type=str,
        default=".",
        help="Path to ARMCortexM-CppLib repository (default: current directory)"
    )
    parser.add_argument(
        "--module",
        type=str,
        default="bit_utils",
        help="Module to test (default: bit_utils). Examples: bit_utils, intrinsics/barriers"
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        default=50.0,
        help="Maximum API cost in USD (default: 50.0)"
    )
    
    args = parser.parse_args()
    
    # Get API key from environment
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Run generator
    generator = AutonomousTestGenerator(
        repo_path=Path(args.repo_path),
        api_key=api_key,
        max_cost=args.max_cost,
        module=args.module
    )
    
    summary = generator.run(args.functions)
    
    # Exit with appropriate code
    sys.exit(0 if summary["all_passed"] else 1)


if __name__ == "__main__":
    main()
