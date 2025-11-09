#!/usr/bin/env python3
"""
Single Agent Test Generator

The simplest, fastest, and most cost-effective mode.
One Claude instance handles the entire workflow.

Usage:
    python single_agent_generator.py \
        --repo /path/to/ARMCortexM-CppLib \
        --function setBit
"""

import os
import sys
from pathlib import Path
import subprocess
from typing import Optional, Dict, Any
import json

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.markdown import Markdown
from anthropic import Anthropic

import config

console = Console()
client = Anthropic(api_key=config.ANTHROPIC_API_KEY)


class TestGenerator:
    """Single-agent test generator"""
    
    def __init__(self, repo_path: Path, function_name: str):
        self.repo_path = Path(repo_path)
        self.function_name = function_name
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        
    def read_file(self, relative_path: str) -> str:
        """Read a file from the repository"""
        full_path = self.repo_path / relative_path
        try:
            with open(full_path, 'r') as f:
                return f.read()
        except Exception as e:
            return f"Error reading {relative_path}: {e}"
    
    def write_file(self, relative_path: str, content: str) -> bool:
        """Write content to a file"""
        full_path = self.repo_path / relative_path
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            return True
        except Exception as e:
            console.print(f"[red]Error writing {relative_path}: {e}[/red]")
            return False
    
    def call_claude(self, prompt: str, max_tokens: int = 8000) -> str:
        """Make an API call to Claude"""
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=max_tokens,
            temperature=config.TEMPERATURE["simple"],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Track token usage
        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens
        
        return response.content[0].text
    
    def generate_test(self) -> Optional[str]:
        """Generate the test file"""
        
        console.print("\n[bold cyan]Step 1: Reading existing patterns...[/bold cyan]")
        
        # Read existing test pattern
        existing_test = self.read_file("tests/bit_utils/test_is_bit_set_runtime.cpp")
        if "Error" in existing_test:
            console.print(f"[red]{existing_test}[/red]")
            return None
        
        # Read the header file
        header = self.read_file("bit_utils.hpp")
        if "Error" in header:
            console.print(f"[red]{header}[/red]")
            return None
        
        console.print("[green]✓ Read existing patterns[/green]")
        
        console.print("\n[bold cyan]Step 2: Generating test code...[/bold cyan]")
        
        prompt = f"""You are an expert in ARM Cortex-M assembly and C++ embedded systems testing.

TASK: Generate a comprehensive test file for the {self.function_name}() function.

CONTEXT:
Here's the function definition from bit_utils.hpp:
```cpp
{header}
```

Here's an example test file showing the pattern to follow:
```cpp
{existing_test}
```

REQUIREMENTS:
1. Create test_{self.function_name.lower()}_runtime.cpp
2. Follow the EXACT pattern from test_is_bit_set_runtime.cpp
3. Test all integer types: uint8_t, uint16_t, uint32_t, uint64_t, int8_t, int16_t, int32_t, int64_t
4. For each type, test bit positions: 0, middle bit, MSB
5. Include CHECK directives for all three optimization levels: DEBUG, MINSIZE, MAXSPEED
6. Use extern "C" [[gnu::naked]] for all test functions
7. Remember: {self.function_name} modifies a reference (T& value), so assembly will include memory operations

CRITICAL REMINDERS:
- For signed types checking MSB: bit 7 of int8_t and bit 15 of int16_t become bit 31 after sign extension
- MAXSPEED optimization adds NOP padding for alignment
- Each function ends with CHECK-EMPTY:
- Group tests by type with clear section headers

OUTPUT: The complete C++ test file, nothing else. No explanations, just code."""

        test_code = self.call_claude(prompt)
        console.print("[green]✓ Generated test code[/green]")
        
        return test_code
    
    def compile_and_test(self, test_name: str, optimization: str = "Debug") -> Dict[str, Any]:
        """Compile and run tests"""
        preset = f"m0-gcc-{optimization.lower()}"
        
        try:
            # Configure
            result = subprocess.run(
                ["cmake", "--preset", preset],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                return {"success": False, "error": f"CMake configure failed: {result.stderr}"}
            
            # Build
            result = subprocess.run(
                ["cmake", "--build", "--preset", preset, "--target", test_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                return {"success": False, "error": f"Build failed: {result.stderr}"}
            
            # Run tests
            result = subprocess.run(
                ["ctest", "--preset", preset, "-R", test_name, "-V"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Compilation timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def read_assembly(self, test_name: str, optimization: str = "Debug") -> str:
        """Read generated assembly"""
        preset = f"m0-gcc-{optimization.lower()}"
        asm_path = self.repo_path / "build" / preset / "tests" / "bit_utils" / f"{test_name}.asm"
        
        if not asm_path.exists():
            return f"Assembly file not found: {asm_path}"
        
        with open(asm_path, 'r') as f:
            return f.read()
    
    def fix_check_directives(self, test_code: str, test_name: str) -> Optional[str]:
        """Fix CHECK directives based on actual assembly"""
        
        console.print("\n[bold cyan]Step 4: Analyzing assembly and fixing CHECK directives...[/bold cyan]")
        
        # Read assembly for all optimization levels
        assemblies = {}
        for opt in ["Debug", "MinSize", "MaxSpeed"]:
            asm = self.read_assembly(test_name, opt)
            if "not found" not in asm:
                assemblies[opt] = asm
        
        if not assemblies:
            console.print("[red]No assembly files found![/red]")
            return None
        
        prompt = f"""You are an expert in ARM assembly and FileCheck directives.

TASK: Fix the CHECK directives in the test file to match the actual assembly output.

TEST FILE:
```cpp
{test_code}
```

ACTUAL ASSEMBLY OUTPUTS:

Debug:
```
{assemblies.get('Debug', 'N/A')}
```

MinSize:
```
{assemblies.get('MinSize', 'N/A')}
```

MaxSpeed:
```
{assemblies.get('MaxSpeed', 'N/A')}
```

REQUIREMENTS:
1. Update ALL CHECK directives to match the actual assembly
2. Keep the exact same structure and test functions
3. Only change the CHECK-NEXT: lines to match actual output
4. Remember: MAXSPEED adds NOP padding
5. Keep CHECK-EMPTY: at the end of each function

OUTPUT: The complete corrected test file, nothing else."""

        fixed_code = self.call_claude(prompt)
        console.print("[green]✓ Fixed CHECK directives[/green]")
        
        return fixed_code
    
    def run(self) -> bool:
        """Run the complete generation workflow"""
        
        console.print(Panel.fit(
            f"[bold]Generating tests for {self.function_name}()[/bold]\n"
            f"Repository: {self.repo_path}\n"
            f"Mode: Single Agent",
            title="ARMCortexM-TestGen",
            border_style="cyan"
        ))
        
        # Generate test code
        test_code = self.generate_test()
        if not test_code:
            return False
        
        # Write initial test file
        test_filename = f"test_{self.function_name.lower()}_runtime.cpp"
        test_path = f"tests/bit_utils/{test_filename}"
        test_name = f"test_{self.function_name.lower()}_runtime"
        
        console.print(f"\n[bold cyan]Step 3: Writing and compiling tests...[/bold cyan]")
        
        if not self.write_file(test_path, test_code):
            return False
        
        console.print(f"[green]✓ Wrote {test_path}[/green]")
        
        # Update CMakeLists.txt
        cmake_path = "tests/bit_utils/CMakeLists.txt"
        cmake_content = self.read_file(cmake_path)
        if f"add_asm_test({test_name})" not in cmake_content:
            cmake_content += f"\nadd_asm_test({test_name})\n"
            if not self.write_file(cmake_path, cmake_content):
                return False
            console.print(f"[green]✓ Updated {cmake_path}[/green]")
        
        # Try to compile
        attempts = 0
        while attempts < config.MAX_COMPILATION_ATTEMPTS:
            attempts += 1
            
            console.print(f"\n[yellow]Compilation attempt {attempts}/{config.MAX_COMPILATION_ATTEMPTS}...[/yellow]")
            
            all_passed = True
            for opt in ["Debug", "MinSize", "MaxSpeed"]:
                result = self.compile_and_test(test_name, opt)
                
                if result["success"]:
                    console.print(f"[green]✓ {opt} tests passed[/green]")
                else:
                    console.print(f"[red]✗ {opt} tests failed[/red]")
                    all_passed = False
            
            if all_passed:
                console.print("\n[bold green]✓ All tests passed![/bold green]")
                break
            
            if attempts < config.MAX_COMPILATION_ATTEMPTS:
                # Fix CHECK directives
                fixed_code = self.fix_check_directives(test_code, test_name)
                if fixed_code:
                    test_code = fixed_code
                    self.write_file(test_path, test_code)
                    console.print("[yellow]Retrying with fixed CHECK directives...[/yellow]")
                else:
                    console.print("[red]Failed to fix CHECK directives[/red]")
                    break
        
        # Print cost summary
        self.print_summary(all_passed)
        
        return all_passed
    
    def print_summary(self, success: bool):
        """Print summary of the generation"""
        input_cost = (self.total_input_tokens / 1_000_000) * config.INPUT_TOKEN_COST
        output_cost = (self.total_output_tokens / 1_000_000) * config.OUTPUT_TOKEN_COST
        total_cost = input_cost + output_cost
        
        summary = f"""
[bold]Generation Summary[/bold]

Status: {"[green]SUCCESS ✓[/green]" if success else "[red]FAILED ✗[/red]"}
Function: {self.function_name}()

[bold]Token Usage:[/bold]
  Input:  {self.total_input_tokens:,} tokens (${input_cost:.4f})
  Output: {self.total_output_tokens:,} tokens (${output_cost:.4f})
  Total:  ${total_cost:.4f}

[bold]Output:[/bold]
  Test file: tests/bit_utils/test_{self.function_name.lower()}_runtime.cpp
"""
        
        console.print(Panel(summary, title="Summary", border_style="green" if success else "red"))


@click.command()
@click.option('--repo', required=True, type=click.Path(exists=True),
              help='Path to ARMCortexM-CppLib repository')
@click.option('--function', required=True, help='Function name to generate tests for (e.g., setBit)')
def main(repo: str, function: str):
    """Generate tests using single agent mode"""
    
    if not config.ANTHROPIC_API_KEY:
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable not set[/red]")
        sys.exit(1)
    
    generator = TestGenerator(Path(repo), function)
    success = generator.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
