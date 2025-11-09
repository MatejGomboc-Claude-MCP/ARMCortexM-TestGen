# ARMCortexM-TestGen 🤖⚡

AI-powered autonomous test generator for ARM Cortex-M embedded systems. **Submit before bed, review PR in the morning!**

Claude writes and validates comprehensive assembly tests while you sleep. Perfect for [ARMCortexM-CppLib](https://github.com/MatejGomboc/ARMCortexM-CppLib) and similar embedded C++ projects.

---

## 🎯 What This Does

Generates assembly-verification tests autonomously:

1. 📖 **Learns** from your existing test patterns
2. ✍️ **Writes** comprehensive test code
3. 🔨 **Compiles** across all optimization levels
4. ✅ **Validates** with FileCheck
5. 🔧 **Fixes** CHECK directive mismatches automatically
6. 🔄 **Iterates** until all tests pass
7. 📬 **Creates** PR with finished tests

**Result:** Wake up to production-ready tests! 🌅

---

## 🚀 Quick Start (Two Modes)

### Mode 1: GitHub Actions (Autonomous) ⭐ Recommended

**Perfect for "submit before bed" usage.**

#### Setup (5 minutes, one time):

1. **Add workflow to your library repo:**

```yaml
# .github/workflows/generate-tests.yml
name: Generate Tests with AI

on:
  workflow_dispatch:
    inputs:
      functions:
        description: 'Functions to test (space-separated)'
        required: true
        default: 'setBit clearBit'

jobs:
  generate:
    runs-on: ubuntu-latest
    timeout-minutes: 360
    
    container:
      image: ghcr.io/matejgomboc/armcortexm-cpplib-devenv:latest
      options: --user root
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: matejgomboc-claude-mcp/armcortexm-testgen@main
        with:
          functions: ${{ inputs.functions }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
      
      - uses: peter-evans/create-pull-request@v6
        with:
          title: 'Add tests: ${{ inputs.functions }}'
```

2. **Add your Anthropic API key:**
   - Go to: `Settings` → `Secrets and variables` → `Actions`
   - Click `New repository secret`
   - Name: `ANTHROPIC_API_KEY`
   - Value: `your-key-here`

#### Usage:

```bash
Before bed:
1. Go to: https://github.com/YOUR_USERNAME/ARMCortexM-CppLib/actions
2. Click "Generate Tests with AI"
3. Click "Run workflow"
4. Enter: "setBit clearBit"
5. Click green "Run workflow" button
6. Go to sleep 😴

Next morning:
1. Check email for PR notification
2. Review PR
3. Merge if satisfied
4. Done! ☕
```

**Cost:** FREE (GitHub Actions) + ~$2-5 API per run  
**Time:** You: 30 seconds | AI: 1-3 hours while you sleep

---

### Mode 2: Local Machine

**For quick one-off test generation.**

```bash
# Clone this repo
git clone https://github.com/MatejGomboc-Claude-MCP/ARMCortexM-TestGen
cd ARMCortexM-TestGen

# Install
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key"

# Generate tests
python single_agent_generator.py \
  --repo ~/ARMCortexM-CppLib \
  --function setBit
```

**Cost:** ~$0.50-1.00 per function  
**Time:** 2-5 minutes

---

## 📊 Cost & Time Comparison

| Approach | Time | Cost | When to Use |
|----------|------|------|-------------|
| **Manual** | 2-3 hours | Your time ($100-300) | Never again! |
| **Local Mode** | 5 minutes | $0.50-1.00 | Quick single function |
| **GitHub Actions** | 30 sec + overnight | $2-5 | Multiple functions, unattended |

---

## 🎓 How It Works

### The Autonomous Workflow:

```
You (before bed):
└─> Click "Run workflow" on GitHub

GitHub Actions (overnight):
├─> Spins up VM with your DevEnv
├─> Checks out your repo
└─> Runs autonomous_test_generator.py
    │
    └─> Claude (via Anthropic API):
        ├─> 📖 Read existing test patterns
        ├─> 📖 Read function to test
        ├─> ✍️ Generate test code
        ├─> 🔨 Compile (Debug)
        ├─> ❌ 3 tests failed
        ├─> 🔍 Analyze assembly
        ├─> 🔧 Fix CHECK directives
        ├─> 🔨 Recompile (Debug)
        ├─> ✅ All Debug tests pass
        ├─> 🔨 Compile (MinSize)
        ├─> ✅ All MinSize tests pass
        ├─> 🔨 Compile (MaxSpeed)
        ├─> ✅ All MaxSpeed tests pass
        └─> 📬 Create PR

You (morning):
└─> ☕ Review and merge PR
```

**GitHub Actions = The workstation (hands)**  
**Claude = The brain (intelligence)**

---

## 💡 Example Output

### Input:
```cpp
// bit_utils.hpp
template<std::integral T>
constexpr void setBit(T& value, uint8_t n) {
    value |= T{1} << n;
}
```

### Generated Test (347 lines):
```cpp
// test_set_bit_runtime.cpp
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

// ... 23 more test functions for all types and bit positions ...
```

### Summary:
```
🎉 SUCCESS! All tests pass for setBit()
⏱️  Time: 8.3 minutes
💰 Cost: $1.47
🎟️  Tokens: 18,432 in, 12,891 out
```

---

## 🎯 Features

- ✅ **Pattern Learning** - Learns from existing tests
- ✅ **Multi-Type** - Tests uint8/16/32/64 and int8/16/32/64
- ✅ **Multi-Optimization** - Debug, MinSize (-Os), MaxSpeed (-O3)
- ✅ **Self-Healing** - Fixes CHECK mismatches automatically
- ✅ **ARM Expert** - Handles sign extension, alignment, ABI
- ✅ **Cost Tracking** - Shows API usage and spending
- ✅ **Unattended** - Runs for hours without supervision
- ✅ **Auto PR** - Creates pull request when done

---

## 📈 ROI Analysis

### Traditional Approach:
- **Time per function:** 2-3 hours
- **Your hourly rate:** $50-100
- **Cost per function:** $100-300 of your time

### AI Approach:
- **Time per function:** 30 seconds (you) + overnight (AI)
- **API cost:** $1-2 per function
- **Your cost:** ~$0 of your time

**Savings:** 95-99% time reduction, 98-99% cost reduction! 🚀

---

## 🛠️ Requirements

### For GitHub Actions Mode:
- ✅ Public repo (or GitHub Actions minutes)
- ✅ Anthropic API key
- ✅ Docker DevEnv (you already have!)

### For Local Mode:
- Python 3.9+
- ARM toolchain (arm-none-eabi-gcc)
- CMake
- FileCheck (from LLVM)
- Anthropic API key

---

## 📚 Documentation

### Files in This Repo:

```
ARMCortexM-TestGen/
├── autonomous_test_generator.py    # Main autonomous script
├── single_agent_generator.py       # Local usage script
├── action.yml                      # GitHub Action definition
├── .github/workflows/
│   └── example-workflow.yml        # Example for your repo
├── requirements.txt
└── README.md
```

### Usage Examples:

**GitHub Actions (Multiple Functions):**
```yaml
with:
  functions: 'setBit clearBit toggleBit'
  max-cost: '20'
```

**Local (Single Function):**
```bash
python single_agent_generator.py \
  --repo ~/ARMCortexM-CppLib \
  --function setBit
```

---

## 🤝 Contributing

This tool is designed for [ARMCortexM-CppLib](https://github.com/MatejGomboc/ARMCortexM-CppLib) but can be adapted for any ARM Cortex-M C++ library with FileCheck-based assembly tests.

Contributions welcome!

---

## 📄 License

Apache 2.0 - Same as ARMCortexM-CppLib

---

## 🙏 Credits

Built by Claude (Anthropic) to support [@MatejGomboc](https://github.com/MatejGomboc)'s excellent [ARMCortexM-CppLib](https://github.com/MatejGomboc/ARMCortexM-CppLib).

**Architecture:**
- **GitHub Actions** = The workstation where Claude does development
- **Claude Sonnet 4.5** = Single autonomous agent that writes, compiles, validates, and fixes tests
- **Your DevEnv Docker** = Pre-configured ARM development environment

---

## 🚀 Future Enhancements

- [ ] Multi-agent crew mode (if single agent needs help)
- [ ] Support for more test types (performance, edge cases)
- [ ] Multi-architecture support (M0, M0+, M3, M4, M7, M33)
- [ ] Automatic regression detection
- [ ] VS Code extension

---

## ❓ FAQ

**Q: Is GitHub Actions free?**  
A: Yes for public repos! Private repos get 2,000 minutes/month free.

**Q: How long does it take?**  
A: 1-3 hours for a couple functions. You sleep through it!

**Q: What if tests fail after 3 attempts?**  
A: The PR will note failures. You can review and fix manually, or re-run.

**Q: Can I use multiple Claude agents?**  
A: Currently single agent (simpler, cheaper). Multi-agent crew can be added if needed.

**Q: What about security?**  
A: Your API key is stored as a GitHub Secret. Code runs in isolated container.

**Q: Can this work for other embedded projects?**  
A: Yes! Designed for ARMCortexM-CppLib but adaptable to similar projects.

---

**Stop writing assembly tests manually. Let Claude do it overnight!** 🤖⚡

[Get Started →](#-quick-start-two-modes) | [View Example Workflow](.github/workflows/example-workflow.yml)
