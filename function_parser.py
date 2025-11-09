#!/usr/bin/env python3
"""
Function Signature Parser

Parses C++ function signatures from header files to determine:
- Function name
- Return type
- Parameters
- Whether function modifies references
- Which test pattern to use
"""

import re
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path


@dataclass
class FunctionSignature:
    """Represents a parsed C++ function signature"""
    name: str
    return_type: str
    parameters: List[str]
    modifies_reference: bool
    is_template: bool
    template_params: List[str]
    
    @property
    def pattern_file(self) -> str:
        """Determine which test pattern file to use"""
        if self.return_type == "void":
            return "test_set_bit_runtime.cpp"  # void-modifying functions
        elif self.return_type == "bool" or "bool" in self.return_type:
            return "test_is_bit_set_runtime.cpp"  # bool-returning functions
        else:
            return "test_set_bit_runtime.cpp"  # default to void pattern
    
    @property
    def test_type(self) -> str:
        """Determine test type for prompt generation"""
        if self.return_type == "void":
            return "void-modifying"
        elif self.return_type == "bool" or "bool" in self.return_type:
            return "bool-returning"
        else:
            return "value-returning"


class FunctionParser:
    """Parser for C++ function signatures"""
    
    def __init__(self, header_content: str):
        self.header_content = header_content
        # Remove comments to avoid false matches
        self.cleaned_content = self._remove_comments(header_content)
    
    def _remove_comments(self, content: str) -> str:
        """Remove C++ comments from content"""
        # Remove single-line comments
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        # Remove multi-line comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        return content
    
    def find_function(self, function_name: str) -> Optional[FunctionSignature]:
        """Find and parse a function signature by name"""
        
        # Pattern to match function declarations/definitions
        # Matches: [template<...>] [constexpr] [inline] return_type function_name(params)
        pattern = rf'''
            (?:template\s*<([^>]+)>\s*)?          # Optional template parameters
            (?:constexpr\s+)?                      # Optional constexpr
            (?:inline\s+)?                         # Optional inline
            (?:static\s+)?                         # Optional static
            (\w+(?:\s*::\s*\w+)*)\s+              # Return type (including namespace)
            ({re.escape(function_name)})\s*       # Function name
            \(([^)]*)\)                            # Parameters
        '''
        
        match = re.search(pattern, self.cleaned_content, re.VERBOSE | re.MULTILINE)
        
        if not match:
            return None
        
        template_params_str = match.group(1)
        return_type = match.group(2).strip()
        func_name = match.group(3)
        params_str = match.group(4).strip()
        
        # Parse template parameters
        is_template = template_params_str is not None
        template_params = []
        if is_template:
            template_params = [p.strip() for p in template_params_str.split(',')]
        
        # Parse parameters
        parameters = []
        if params_str:
            # Split by comma, but respect nested templates
            params = self._split_parameters(params_str)
            parameters = [p.strip() for p in params if p.strip()]
        
        # Check if function modifies references
        modifies_reference = any('&' in p and 'const' not in p.lower() 
                               for p in parameters)
        
        return FunctionSignature(
            name=func_name,
            return_type=return_type,
            parameters=parameters,
            modifies_reference=modifies_reference,
            is_template=is_template,
            template_params=template_params
        )
    
    def _split_parameters(self, params_str: str) -> List[str]:
        """
        Split parameter string by comma, respecting nested templates and function pointers.
        
        Bug #14 fix: Now handles function pointer parameters properly.
        """
        params = []
        current = []
        template_depth = 0
        paren_depth = 0
        
        for char in params_str:
            if char == '<':
                template_depth += 1
                current.append(char)
            elif char == '>':
                template_depth -= 1
                current.append(char)
            elif char == '(':
                paren_depth += 1
                current.append(char)
            elif char == ')':
                paren_depth -= 1
                current.append(char)
            elif char == ',' and template_depth == 0 and paren_depth == 0:
                # Only split on commas outside templates and parentheses
                params.append(''.join(current))
                current = []
            else:
                current.append(char)
        
        if current:
            params.append(''.join(current))
        
        return params
    
    def list_all_functions(self) -> List[str]:
        """List all function names found in header"""
        # Pattern to match function names
        pattern = r'(?:template\s*<[^>]+>\s*)?(?:constexpr\s+)?(?:inline\s+)?(?:static\s+)?\w+(?:\s*::\s*\w+)*\s+(\w+)\s*\([^)]*\)'
        
        matches = re.finditer(pattern, self.cleaned_content, re.MULTILINE)
        functions = [m.group(1) for m in matches]
        
        # Filter out constructors, destructors, operators
        functions = [f for f in functions 
                    if not f.startswith('~') 
                    and not f.startswith('operator')
                    and f[0].islower()]  # Usually functions start with lowercase
        
        return list(set(functions))  # Remove duplicates


def validate_function_exists(header_path: Path, function_name: str) -> Optional[FunctionSignature]:
    """
    Validate that a function exists in a header file and return its signature.
    
    Args:
        header_path: Path to the header file
        function_name: Name of the function to find
    
    Returns:
        FunctionSignature if found, None otherwise
    """
    try:
        with open(header_path, 'r') as f:
            content = f.read()
        
        parser = FunctionParser(content)
        signature = parser.find_function(function_name)
        
        return signature
        
    except Exception as e:
        print(f"Error parsing header: {e}")
        return None


def discover_testable_functions(header_path: Path, tests_dir: Path) -> List[str]:
    """
    Discover functions that need tests.
    
    Args:
        header_path: Path to the header file
        tests_dir: Directory containing existing tests
    
    Returns:
        List of function names that don't have tests yet
    """
    try:
        with open(header_path, 'r') as f:
            content = f.read()
        
        parser = FunctionParser(content)
        all_functions = parser.list_all_functions()
        
        # Find functions that already have tests
        tested_functions = set()
        if tests_dir.exists():
            for test_file in tests_dir.glob("test_*_runtime.cpp"):
                # Extract function name from test filename
                # test_set_bit_runtime.cpp -> setBit
                name_part = test_file.stem.replace('test_', '').replace('_runtime', '')
                # Convert snake_case to camelCase
                parts = name_part.split('_')
                func_name = parts[0] + ''.join(p.capitalize() for p in parts[1:])
                tested_functions.add(func_name)
        
        # Return functions without tests
        return [f for f in all_functions if f not in tested_functions]
        
    except Exception as e:
        print(f"Error discovering functions: {e}")
        return []


# Example usage and testing
if __name__ == "__main__":
    # Test the parser
    test_header = """
    // Test header
    
    template<std::integral T>
    constexpr void setBit(T& value, uint8_t n) {
        value |= T{1} << n;
    }
    
    template<std::integral T>
    constexpr bool isBitSet(const T& value, uint8_t n) {
        return (value & (T{1} << n)) != 0;
    }
    
    template<std::integral T>
    constexpr T readBit(const T& value, uint8_t n) {
        return (value >> n) & T{1};
    }
    
    // Bug #14 test: Function pointer parameter
    void registerCallback(void (*callback)(int, int), int data) {
        callback(data, data);
    }
    """
    
    parser = FunctionParser(test_header)
    
    # Test setBit
    sig = parser.find_function("setBit")
    if sig:
        print(f"Function: {sig.name}")
        print(f"Return type: {sig.return_type}")
        print(f"Parameters: {sig.parameters}")
        print(f"Modifies reference: {sig.modifies_reference}")
        print(f"Pattern file: {sig.pattern_file}")
        print(f"Test type: {sig.test_type}")
        print()
    
    # Test isBitSet
    sig = parser.find_function("isBitSet")
    if sig:
        print(f"Function: {sig.name}")
        print(f"Return type: {sig.return_type}")
        print(f"Pattern file: {sig.pattern_file}")
        print(f"Test type: {sig.test_type}")
        print()
    
    # Bug #14 test: Function pointer
    sig = parser.find_function("registerCallback")
    if sig:
        print(f"Function: {sig.name}")
        print(f"Return type: {sig.return_type}")
        print(f"Parameters: {sig.parameters}")
        print(f"Number of params: {len(sig.parameters)}")
        assert len(sig.parameters) == 2, "Should have 2 parameters"
        print("✓ Function pointer parsing works!")
        print()
    
    # List all functions
    print(f"All functions: {parser.list_all_functions()}")
