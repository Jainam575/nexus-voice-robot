# 🗣️ Voice Command Reference

Commands are matched in a fixed priority order; the first match wins.
Anything unmatched falls through to the LLM for free conversation.

## Priority 1 — Safety

| Say | Effect |
|---|---|
| **"STOP!"** / "stop" (urgent tone not required) | Immediate motor stop |

## Priority 2 — Sleep

| Say | Effect |
|---|---|
| "go to sleep" / "sleep mode" | Robot sleeps until it hears its name |
| "hey Nexus" (fuzzy) / "નેક્સસ" | Wakes it up |

The wake matcher accepts any word within edit distance 3 of "nexus",
because speech-to-text frequently renders it as "hey nex", "hey nex S",
"hey macus", "hey next", "lexus", "nexa", …

## Priority 3 — Navigation

| Say | Effect |
|---|---|
| "find the bottle" / "go to the <object>" | Vision-guided drive to the object |

The robot looks for the object with its offline detector (COCO classes),
falls back to asking the cloud VLM *left/center/right/no*, turns toward it,
approaches in short steps with an obstacle check before each forward move,
and announces when the VLM confirms it's close.

## Priority 4 — Movement

| Say | Effect |
|---|---|
| "move forward" (optionally "for 3 seconds" / "for 2 steps") | Drive forward |
| "move backward" / "move back" | Drive backward |
| "turn left" / "turn right" | Turn |
| "spin" / "spin around" | 360° spin |
| "stop" | Stop |

Numbers can be spoken ("for three seconds") or digits ("for 3 seconds").

## Priority 5 — Special commands

| Say | Effect |
|---|---|
| "demo" → **"confirm"** | Guided demo mode (weather + news + movement sequence) |
| "guard mode" / "security mode" | Motion/people watching with voice alerts |
| "dance" | Little movement dance |
| "who am I" / "recognize me" / "do you know me" | Face recognition |
| "remember my face as <name>" / "learn my face" / "save my face" | Face enrollment (~12 samples) |
| "delete my face" / "delete face" | Remove one person |
| "delete all faces" / "wipe faces" | Clear all face data |
| "play a game" / "let's play" | Game menu (rock-paper-scissors, trivia…) |
| "weather" / "forecast" / "is it raining" / "how hot" | Live weather (Open-Meteo) |
| "news" / "headlines" | News (Google News RSS) |
| "what do you remember about me" | Memory recall |
| "forget everything" / "clear your memory" | Memory wipe |
| "how do you feel" / "what's your mood" | Mood report |
| "exit" / "quit" / "shutdown" / "bye" | Clean shutdown |
| identity triggers ("who are you", "who made you"…) | Self-introduction |

## Priority 6 — Vision questions

Ask about what the robot sees — in English or Gujarati:

- "what do you see", "describe the scene"
- **"શું જોઈ રહ્યા છો", "સામે શું છે", "દ્રશ્ય વર્ણન"** …

The camera preview appears on the robot's face while it answers.

## Everything else — conversation

Free-form chat with the LLM. Replies are spoken in
`NEXUS_REPLY_LANGUAGE` (Gujarati in our configuration) and the robot
remembers context within the session.
