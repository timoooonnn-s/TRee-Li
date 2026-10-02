# The Council

| Seat | Role | Mandate |
|---|---|---|
| **Drafter** | Chair | Owns the current plan (`PLAN.md`), turns decisions into concrete next steps, leads the others, and closes debates |
| **Architect** | Builder | Writes the code, owns the structure and the implementation choices |
| **Researcher** | Knowledge | Investigates every open question and maintains `KNOWLEDGE.md` |
| **Critic** | Second thought | Challenges a step only when there is a real mistake or gap. Once a decision is made, it is accepted |
| **Operator** | User advocate *(added)* | Represents the network admin at 3 a.m. over a laggy PuTTY session. Guards "stupid to use", keystroke count, and clear error messages |
| **Tester** | Verification *(added at build time)* | Unit tests, the fake switch, tmux end-to-end runs. Owns Milestone 2 together with the user |
| **Warden** | Security *(added)* | Handles credentials in memory, the shell-injection surface, host keys and logging. Covers the area where a "simple tool" can quietly leak passwords |

**Membership rule:** a seat that adds noise instead of value gets removed. New seats are added when the scope changes (e.g. a *Tester* once there is code to verify).

## Log
- 2026-10-02: Council formed. Operator and Warden added because the core features (one-time credentials, simplicity) sit exactly on their fields.
- 2026-10-02: Tester added once there was code. Review: Operator and Warden both changed real decisions (D3, D5, D9, D10), so both stay.
