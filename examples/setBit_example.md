# Example: Generating Tests for setBit()

This example shows the single-agent mode generating tests for the `setBit()` function.

## Command

```bash
python single_agent_generator.py \
  --repo /path/to/ARMCortexM-CppLib \
  --function setBit
```

## Output

```
╭─────────────────── ARMCortexM-TestGen ────────────────────╮
│ Generating tests for setBit()                            │
│ Repository: /path/to/ARMCortexM-CppLib                   │
│ Mode: Single Agent                                        │
╰───────────────────────────────────────────────────────────╯

Step 1: Reading existing patterns...
✓ Read existing patterns

Step 2: Generating test code...
✓ Generated test code

Step 3: Writing and compiling tests...
✓ Wrote tests/bit_utils/test_set_bit_runtime.cpp
✓ Updated tests/bit_utils/CMakeLists.txt

Compilation attempt 1/3...
✓ Debug tests passed
✓ MinSize tests passed
✓ MaxSpeed tests passed

✓ All tests passed!

╭──────────────── Summary ────────────────╮
│                                          │
│ Generation Summary                       │
│                                          │
│ Status: SUCCESS ✓                        │
│ Function: setBit()                       │
│                                          │
│ Token Usage:                             │
│   Input:  12,450 tokens ($0.0374)       │
│   Output: 8,920 tokens ($0.1338)        │
│   Total:  $0.1712                        │
│                                          │
│ Output:                                  │
│   Test file: tests/bit_utils/            │
│              test_set_bit_runtime.cpp    │
│                                          │
╰──────────────────────────────────────────╯
```

## Generated Test File Structure

```cpp
#include "bit_utils.hpp"

// ============================================================================
// uint8_t tests
// ============================================================================

extern "C" [[gnu::naked]] void test_set_bit_u_8_0(uint8_t& value) {
    Cortex::setBit(value, uint8_t{0});
}

// CHECK-LABEL: <test_set_bit_u_8_0>:
// CHECK-NEXT: ldrb r3, [r0]
// CHECK-NEXT: movs r2, #1
// CHECK-NEXT: orrs r3, r2
// CHECK-NEXT: strb r3, [r0]
// CHECK-EMPTY:

// ... 24 total test functions ...
```

## Time Comparison

| Task | Manual | AI-Generated |
|------|--------|-------------|
| Write test functions | 2-3 hours | 30 seconds |
| Write CHECK directives | 1-2 hours | Automatic |
| Compile and fix errors | 30-60 min | Automatic |
| **Total** | **4-6 hours** | **1-2 minutes** |

## Cost

- **API Cost**: $0.17
- **Your Time Saved**: 4-6 hours
- **ROI**: 14,000% - 21,000%
