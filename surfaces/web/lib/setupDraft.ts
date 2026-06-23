/* ============================================================================
   lib/setupDraft.ts — Vidya's drafts for the admin blueprint wizard.

   Vidya may PREPARE a structure and a starter roster (the `prepare` ladder
   stage). It never commits them: the human reviews and approves, and only then
   does saveSchool persist the blueprint. All labels are generic — never a real
   personal name, never a real board lock-in, never real pricing.
   ============================================================================ */

import { mintId, type GroupNode, type RosterMember, type SchoolSetup } from './store';

/** A suggested, board-agnostic structure: one campus, two grades, two sections. */
export function draftStructure(): GroupNode[] {
  const sectionA = { id: mintId(), name: 'Section A' };
  const sectionB = { id: mintId(), name: 'Section B' };
  const sectionC = { id: mintId(), name: 'Section A' };
  return [
    {
      id: mintId(),
      name: 'Campus North',
      grades: [
        {
          id: mintId(),
          name: 'Grade 9',
          sections: [
            { ...sectionA, teacherLabel: 'Teacher 1' },
            { ...sectionB, teacherLabel: 'Teacher 2' },
          ],
        },
        {
          id: mintId(),
          name: 'Grade 10',
          sections: [{ ...sectionC, teacherLabel: 'Teacher 3' }],
        },
      ],
    },
  ];
}

/** A starter roster Vidya drafts for a structure — generic labels only. */
export function draftRoster(structure: GroupNode[]): RosterMember[] {
  const out: RosterMember[] = [];
  let studentIndex = 0;
  let teacherIndex = 0;
  const letters = 'ABCDEFGHIJKLMNOP';
  for (const group of structure) {
    for (const grade of group.grades) {
      for (const section of grade.sections) {
        teacherIndex += 1;
        out.push({
          id: mintId(),
          label: `Teacher ${teacherIndex}`,
          kind: 'teacher',
          sectionId: section.id,
        });
        // A handful of generic students per section.
        for (let i = 0; i < 3; i += 1) {
          const label = `Student ${letters[studentIndex % letters.length]}`;
          studentIndex += 1;
          out.push({ id: mintId(), label, kind: 'student', sectionId: section.id });
        }
      }
    }
  }
  return out;
}

/** Count the leaves of a structure, for the plain-language review. */
export function countStructure(structure: GroupNode[]): {
  groups: number;
  grades: number;
  sections: number;
} {
  let grades = 0;
  let sections = 0;
  for (const g of structure) {
    grades += g.grades.length;
    for (const gr of g.grades) sections += gr.sections.length;
  }
  return { groups: structure.length, grades, sections };
}

/** Assemble the full blueprint from the approved drafts. Not yet persisted. */
export function assembleSchool(input: {
  name: string;
  board: string;
  pacing: string;
  structure: GroupNode[];
  roster: RosterMember[];
}): SchoolSetup {
  return {
    institution: {
      id: mintId(),
      name: input.name,
      board: input.board,
      pacing: input.pacing,
      createdAt: new Date().toISOString(),
    },
    structure: input.structure,
    roster: input.roster,
    confirmed: true,
  };
}
