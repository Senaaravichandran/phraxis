# PHRAXIS - 3-Minute Hackathon Demo Script

**Total Duration: 3:00 (180 seconds)**

---

## [0:00-0:15] Introduction (15 seconds)

"Hi everyone! I'm here to show you PHRAXIS — a voice-powered AI coding assistant that turns spoken feature requests into production-ready code and GitHub pull requests in under 4 minutes. Let me show you how it works."

[Stage Direction: Show PHRAXIS dashboard on screen]

---

## [0:15-0:45] The Problem (30 seconds)

"Developers waste hours every day on repetitive coding tasks. You have an idea — maybe adding rate limiting, or a new API endpoint — but you need to read through dozens of files, understand the codebase architecture, write the code, write tests, and create a PR. This takes 2-3 hours minimum, even for experienced developers. What if you could just *speak* your idea and have AI do all of that for you?"

[Stage Direction: Show frustrated developer image or animation]

---

## [0:45-1:15] The Solution Overview (30 seconds)

"PHRAXIS solves this with a powerful IBM AI pipeline. IBM Watson Speech-to-Text captures your voice. Watson Natural Language Understanding extracts structured intent. Then — and this is the magic — IBM Bob, the AI coding agent, reads your entire codebase using Architect mode, creates an implementation plan, generates the actual code files, and opens a GitHub PR. All powered by IBM watsonx and IBM Cloudant for storage. Let's see it in action."

[Stage Direction: Show architecture diagram or flow visualization]

---

## [1:15-2:45] Live Demo (90 seconds)

### [1:15-1:25] Setup (10 seconds)
"Here's our demo repository — a Python payment service. I want to add rate limiting. Watch this."

[Stage Direction: Show demo_repo structure briefly]

### [1:25-1:35] Voice Capture (10 seconds)
"I'll click the microphone and speak my feature request."

[Stage Direction: Click microphone button, show recording indicator]

### [1:35-1:50] Speaking (15 seconds)
[Speak clearly into microphone]: 
"Add rate limiting — 100 requests per minute for free users and 1000 for premium. Return 429 with a retry-after header."

[Stage Direction: Show audio waveform visualization]

### [1:50-2:05] Transcript Display (15 seconds)
"IBM Watson Speech-to-Text transcribed that perfectly. Now watch as Watson Natural Language Understanding extracts the structured intent — it identified the action, parameters, constraints, and exactly where in the codebase this needs to go."

[Stage Direction: Show transcript panel, then intent graph visualization with D3.js]

### [2:05-2:30] Bob Working (25 seconds)
"Now IBM Bob takes over. In Architect mode, Bob is reading every file in our payment service — understanding the structure, dependencies, and patterns. In Plan mode, Bob creates a step-by-step implementation plan. And in Code mode, Bob is writing the actual middleware, updating the app configuration, and generating comprehensive tests. All happening in real-time."

[Stage Direction: Show LiveCodePanel with streaming code generation, files being created]

### [2:30-2:45] PR Created (15 seconds)
"And there it is! A complete GitHub pull request with all the code changes, tests included, and an AI-generated description explaining exactly what was implemented. From voice to PR in under 4 minutes. This is production-ready code."

[Stage Direction: Show GitHub PR page with diff, files changed, and AI description]

---

## [2:45-3:15] Impact & IBM Technology (30 seconds)

"PHRAXIS transforms developer productivity. What took 2-3 hours now takes 4 minutes. This is powered entirely by IBM's AI ecosystem: Watson Speech-to-Text for voice, Watson NLU for intent extraction, IBM Bob for autonomous code generation, watsonx for AI orchestration, and Cloudant for data storage. Every component is IBM technology working together seamlessly. Imagine scaling this across your entire development team — that's hundreds of hours saved every week."

[Stage Direction: Show impact metrics or team productivity visualization]

---

## [3:15-3:20] Closing (5 seconds)

"PHRAXIS — speak your code into existence. Thank you!"

[Stage Direction: Show PHRAXIS logo and team contact info]

---

## Timing Notes

- **Total word count**: ~450 words
- **Speaking pace**: 150 words per minute (natural, enthusiastic pace)
- **Actual speaking time**: ~3:00 minutes
- **Buffer**: Built-in pauses for screen transitions and audience reaction

## Key Emphasis Points

1. **IBM Technologies** (mentioned 8+ times):
   - IBM Watson Speech-to-Text
   - IBM Watson Natural Language Understanding
   - IBM Bob (AI coding agent)
   - IBM watsonx
   - IBM Cloudant

2. **Time Savings**: "2-3 hours → 4 minutes" (repeated twice)

3. **Production-Ready**: Emphasize this is real, deployable code

4. **Live Demo**: The core 90 seconds should feel dynamic and exciting

## Delivery Tips

- **Energy Level**: High enthusiasm, especially during live demo
- **Pace**: Slightly faster during problem/solution, slower during demo for clarity
- **Pauses**: Natural pauses after "Let me show you how it works" and "Watch this"
- **Voice Modulation**: Emphasize "IBM" each time, stress "4 minutes" and "production-ready"
- **Eye Contact**: Look at judges during intro/closing, screen during demo
- **Backup Plan**: If live demo fails, have screen recording ready

## Screen Layout Recommendation

- **Split screen**: Dashboard on left, terminal/logs on right during demo
- **Full screen**: GitHub PR at the end for maximum impact
- **Transitions**: Smooth, no more than 2 seconds between sections

---

**Practice this script 5+ times before the demo. Time yourself. Adjust pace as needed. You've got this! 🚀**