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

try:
    import anthropic
except ImportError:
    print("Installing anthropic package...")
    subprocess.run([sys.executable, "-m", "pip", "install", "anthropic"], check=True)
    import anthropic


class AutonomousTestGenerator:
    """Single Claude agent that generates, compiles, and validates tests autonomously"""
    
    def __init__(self, repo_path: Path, api_key: str, max_cost: float = 50.0):
        self.repo_path = Path(repo_path)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.max_cost = max_cost
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        
        # Cost per 1M tokens
        self.input_cost_per_million = 3.0
        self.output_cost_per_million = 15.0
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate API cost"""
        input_cost = (input_tokens / 1_000_000) * self.input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * self.output_cost_per_million
        return input_cost + output_cost
    
    def call_claude(self, prompt: str, max_tokens: int = 8000) -> str:
        """Make API call to Claude"""
        print(f"\n🤖 Calling Claude API...")
        
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
        
        print(f"   Input tokens: {response.usage.input_tokens:,}")
        print(f"   Output tokens: {response.usage.output_tokens:,}")
        print(f"   Call cost: ${cost:.4f}")
        print(f"   Total cost so far: ${self.total_cost:.4f}")
        
        if self.total_cost > self.max_cost:
            raise RuntimeError(f"Cost limit ${self.max_cost} exceeded!")
        
        return response.content[0].text
    
    def read_file(self, relative_path: str) -> str:
        """Read file from repo"""
        file_path = self.repo_path / relative_path
        if not file_path.exists():
            return f"ERROR: File not found: {relative_path}"
        return file_path.read_text()
    
    def write_file(self, relative_path: str, content: str) -> bool:
        """Write file to repo"""
        file_path = self.repo_path / relative_path
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            return True
        except Exception as e:
            print(f"❌ Error writing {relative_path}: {e}")
            return False
    
    def compile_and_test(self, test_name: str, optimization: str) -> Dict[str, Any]:
        """Compile and run tests for a specific optimization level"""
        preset = f"m0-gcc-{optimization.lower()}"
        
        print(f"\n🔨 Compiling {optimization}...")
        
        # Configure
        result = subprocess.run(
            ["cmake", "--preset", preset],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
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
        
        return {
            "success": result.returncode == 0,
            "stage": "test",
            "output": result.stdout + "\n" + result.stderr
        }
    
    def read_assembly(self, test_name: str, optimization: str) -> str:
        """Read generated assembly file"""
        preset = f"m0-gcc-{optimization.lower()}"
        asm_path = self.repo_path / "build" / preset / "tests" / "bit_utils" / f"{test_name}.asm"
        
        if not asm_path.exists():
            return f"ERROR: Assembly file not found: {asm_path}"
        
        return asm_path.read_text()
    
    def generate_test(self, function_name: str) -> bool:
        """Generate and validate tests for a single function"""
        
        print(f"\n{'='*70}")
        print(f"🎯 GENERATING TESTS FOR {function_name}()")
        print('='*70)
        
        # Read context
        print("\n📖 Reading existing patterns...")
        existing_test = self.read_file("tests/bit_utils/test_is_bit_set_runtime.cpp")
        if existing_test.startswith("ERROR"):
            print(f"❌ {existing_test}")
            return False
        
        header = self.read_file("bit_utils.hpp")
        if header.startswith("ERROR"):
            print(f"❌ {header}")
            return False
        
        print(f"   ✓ Read test pattern ({len(existing_test)} bytes)")
        print(f"   ✓ Read header file ({len(header)} bytes)")
        
        # Generate initial test
        print(f"\n🤖 Generating test code for {function_name}()...")
        
        prompt = f"""You are an expert in ARM Cortex-M assembly and C++ embedded systems testing.

TASK: Generate test_{function_name.lower()}_runtime.cpp following the EXACT pattern.

HEADER FILE (bit_utils.hpp):
```cpp
{header}
```

PATTERN TO FOLLOW (test_is_bit_set_runtime.cpp):
```cpp
{existing_test}
```

REQUIREMENTS:
1. Test all integer types: uint8_t, uint16_t, uint32_t, uint64_t, int8_t, int16_t, int32_t, int64_t
2. For each type, test bit positions: 0, middle bit, MSB
3. Include CHECK directives for DEBUG, MINSIZE, MAXSPEED optimizations
4. Use extern "C" [[gnu::naked]] for all test functions
5. Remember: {function_name} modifies a reference (T& value), so assembly will include memory operations
6. For signed types checking MSB: bit 7 of int8_t and bit 15 of int16_t become bit 31 after sign extension
7. MAXSPEED optimization adds NOP padding for alignment
8. Each function ends with CHECK-EMPTY:

OUTPUT: The complete C++ test file only. No explanations, no markdown, just the raw C++ code."""

        test_code = self.call_claude(prompt)
        
        # Write test file
        test_filename = f"test_{function_name.lower()}_runtime.cpp"
        test_path = f"tests/bit_utils/{test_filename}"
        test_name = f"test_{function_name.lower()}_runtime"
        
        print(f"\n✍️  Writing {test_path}...")
        if not self.write_file(test_path, test_code):
            return False
        print(f"   ✓ Wrote {test_path}")
        
        # Update CMakeLists.txt
        cmake_path = "tests/bit_utils/CMakeLists.txt"
        cmake_content = self.read_file(cmake_path)
        if f"add_asm_test({test_name})" not in cmake_content:
            cmake_content += f"\nadd_asm_test({test_name})\n"
            self.write_file(cmake_path, cmake_content)
            print(f"   ✓ Updated CMakeLists.txt")
        
        # Try to compile and test (with retries)
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            print(f"\n{'─'*70}")
            print(f"🔄 ATTEMPT {attempt}/{max_attempts}")
            print('─'*70)
            
            all_passed = True
            failed_optimizations = []
            
            for optimization in ["Debug", "MinSize", "MaxSpeed"]:
                result = self.compile_and_test(test_name, optimization)
                
                if result["success"]:
                    print(f"   ✅ {optimization} tests passed")
                else:
                    print(f"   ❌ {optimization} tests failed at {result['stage']}")
                    all_passed = False
                    failed_optimizations.append((optimization, result))
            
            if all_passed:
                print(f"\n🎉 SUCCESS! All tests pass for {function_name}()")
                return True
            
            if attempt < max_attempts:
                print(f"\n🔧 Fixing failures...")
                
                # Collect assembly for failed optimizations
                assemblies = {}
                for opt, result in failed_optimizations:
                    if result["stage"] == "test":  # Only if we got to testing
                        asm = self.read_assembly(test_name, opt)
                        if not asm.startswith("ERROR"):
                            assemblies[opt] = asm
                
                if not assemblies:
                    print("   ❌ No assembly available to analyze")
                    continue
                
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
                
                print(f"\n✍️  Writing corrected version...")
                self.write_file(test_path, test_code)
                print(f"   ✓ Updated {test_path}")
        
        print(f"\n❌ FAILED: Could not get tests passing after {max_attempts} attempts")
        return False
    
    def run(self, functions: List[str]) -> Dict[str, Any]:
        """Run autonomous test generation for multiple functions"""
        
        print("\n" + "="*70)
        print("🤖 AUTONOMOUS TEST GENERATOR")
        print("="*70)
        print(f"Functions to test: {', '.join(functions)}")
        print(f"Max cost: ${self.max_cost}")
        print("="*70)
        
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
                print(f"\n❌ ERROR: {e}")
                results[func] = {
                    "success": False,
                    "error": str(e)
                }
                break
        
        elapsed = time.time() - start_time
        
        # Print summary
        print("\n" + "="*70)
        print("📊 FINAL SUMMARY")
        print("="*70)
        
        for func, result in results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"{status} - {func}()")
            if result["error"]:
                print(f"       Error: {result['error']}")
        
        print(f"\n⏱️  Time: {elapsed/60:.1f} minutes")
        print(f"💰 Cost: ${self.total_cost:.2f}")
        print(f"🎟️  Tokens: {self.total_input_tokens:,} in, {self.total_output_tokens:,} out")
        print("="*70)
        
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
        "--max-cost",
        type=float,
        default=50.0,
        help="Maximum API cost in USD (default: 50.0)"
    )
    
    args = parser.parse_args()
    
    # Get API key from environment
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Run generator
    generator = AutonomousTestGenerator(
        repo_path=Path(args.repo_path),
        api_key=api_key,
        max_cost=args.max_cost
    )
    
    summary = generator.run(args.functions)
    
    # Exit with appropriate code
    sys.exit(0 if summary["all_passed"] else 1)


if __name__ == "__main__":
    main()
