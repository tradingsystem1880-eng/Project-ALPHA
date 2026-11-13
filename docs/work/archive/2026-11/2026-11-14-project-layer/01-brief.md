# The file system explains what each part is for

## What the owner wants

"ensure file system set up is also set up for overall project as well. So when we are building
features and working on project we don't run into issues or problems. For example if the file
system was set up correctly you would have been able to understand exactly the thought,
reasoning, expected plan, location etc for rd agents. That's the purpose of the file system."

In one sentence: an agent starting from `CLAUDE.md` must be able to find, quickly, why each major
part of ALPHA exists, how it is meant to work, what is real, where it lives, what is next, what
must never be done to it, and what the owner has decided about it.

## What done looks like

- One short file per major part, all with the same headings, plus a one-page overview of the
  research loop and a dated log of the owner's own words.
- Every routing file points to them, and a test keeps them complete.
- A fresh agent asked "should RD-Agent be shelved because it is not installed?" answers "no, and
  here is why", in a small read.

## How they will see it

Open `docs/reference/project/overview.md` on GitHub. Nothing changes in the app.

## Out of scope

No product code. No edits to the capability map, the triage sheet, existing task folders, the
research stage folders or protected checks. No owner decisions are made here; open questions are
listed for the owner.
