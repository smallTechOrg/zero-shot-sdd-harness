# Philosophy

This is a **spec-driven-development (SDD) coding-agent harness**: a disciplined method
for building software with AI, where human intent and machine action stay continuously
reconciled. The core objective of the harness is to **minimize the distance between intent and outcome**.


## Spec Driven Development

The harness views the ideal SDD process as made of of four fundamental layers:

| Layer      | Question | Artefacts |
|------------|-----------------|---|
| Intention    | what should this system be?      | Spec |
| Action     | what is the system designed to do right now?     | Code |
| Outcome   | what does the system actually do? | Logs |
| Awareness | how do we get the system to do what it should do? | Harness |

The first three layers (intention, action & outcome) are the **sources of truth** about the system from different perspectives; the fourth (awareness)
is the practice that makes sense of the truth and corrects course.


## Awareness Loop

    spec (intention) ──▶ code (action) ──▶ logs (outcome)
       ▲                                   │
       └──────────── harness ◀─────────────┘
            observe drift, adjust intention or action


## Process

A `supervisor` (the primary agent) runs a co-ordinated pipeline with the help of specialist agents:
- **researcher** → understands intent, frames as requirements.
- **planner** → breaks down requirements into feasible plan.
- **executor** → executes each step of plan, till delivery.
- **reviewer** → raises the bar on delivery, challenges solution, forces improvement.
- **deployer** → ships demos on local, or manages deployment based on phase of delivery.
- **analyser** → observes logs, metrics, user prompts, performance of agents, co-ordinates with supervisor.

The supervisor will co-ordinate this team of specialists based on the goal, task and workflow.


## Principles

1. **Humans author intent.** The core spec should be written by the user. The researcher
   can ask questions and help user write, but the words of core intent should be owned by the user.
2. **Spec should always stay up to date.** Spec should be continuously updated to capture what the code & logs are saying.
