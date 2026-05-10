import {
  Document,
  Paragraph,
  TextRun,
  HeadingLevel,
  Table,
  TableRow,
  TableCell,
  WidthType,
  BorderStyle,
  AlignmentType,
} from "docx";
import type { MinutesReport } from "@/components/ReportRenderer";

/**
 * Generate a Word (.docx) document from a MinutesReport.
 * Returns a Blob ready for download.
 */
export async function generateDocx(report: MinutesReport): Promise<Blob> {
  const { Packer } = await import("docx");

  const children: (Paragraph | Table)[] = [];

  // Title
  children.push(
    new Paragraph({
      text: report.meeting_title,
      heading: HeadingLevel.TITLE,
      spacing: { after: 200 },
    })
  );

  // Date & Participants
  children.push(
    new Paragraph({
      children: [
        new TextRun({ text: "Date: ", bold: true }),
        new TextRun(new Date(report.meeting_datetime).toLocaleString()),
      ],
      spacing: { after: 100 },
    })
  );
  children.push(
    new Paragraph({
      children: [
        new TextRun({ text: "Participants: ", bold: true }),
        new TextRun(report.participants.join(", ")),
      ],
      spacing: { after: 300 },
    })
  );

  // Summary
  children.push(
    new Paragraph({ text: "Summary", heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 200 } })
  );
  children.push(
    new Paragraph({ text: report.summary, spacing: { after: 300 } })
  );

  // Key Discussion Points
  if (report.key_discussion_points.length > 0) {
    children.push(
      new Paragraph({ text: "Key Discussion Points", heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 200 } })
    );
    for (const point of report.key_discussion_points) {
      children.push(
        new Paragraph({ text: point, bullet: { level: 0 }, spacing: { after: 80 } })
      );
    }
  }

  // Decisions
  if (report.decisions.length > 0) {
    children.push(
      new Paragraph({ text: "Decisions", heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 200 } })
    );

    const decisionRows = [
      new TableRow({
        children: [
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Decision", bold: true })] })], width: { size: 35, type: WidthType.PERCENTAGE } }),
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Rationale", bold: true })] })], width: { size: 35, type: WidthType.PERCENTAGE } }),
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Owner", bold: true })] })], width: { size: 15, type: WidthType.PERCENTAGE } }),
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Evidence", bold: true })] })], width: { size: 15, type: WidthType.PERCENTAGE } }),
        ],
      }),
      ...report.decisions.map(
        (d) =>
          new TableRow({
            children: [
              new TableCell({ children: [new Paragraph(d.decision)] }),
              new TableCell({ children: [new Paragraph(d.rationale)] }),
              new TableCell({ children: [new Paragraph(d.owner || "—")] }),
              new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: d.evidence, italics: true, size: 18 })] })] }),
            ],
          })
      ),
    ];

    children.push(
      new Table({
        rows: decisionRows,
        width: { size: 100, type: WidthType.PERCENTAGE },
      })
    );
  }

  // Action Items
  if (report.action_items.length > 0) {
    children.push(
      new Paragraph({ text: "Action Items", heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 200 } })
    );

    const actionRows = [
      new TableRow({
        children: [
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Task", bold: true })] })], width: { size: 35, type: WidthType.PERCENTAGE } }),
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Owner", bold: true })] })], width: { size: 15, type: WidthType.PERCENTAGE } }),
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Due Date", bold: true })] })], width: { size: 15, type: WidthType.PERCENTAGE } }),
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Priority", bold: true })] })], width: { size: 10, type: WidthType.PERCENTAGE } }),
          new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Confidence", bold: true })] })], width: { size: 10, type: WidthType.PERCENTAGE } }),
        ],
      }),
      ...report.action_items.map(
        (a) =>
          new TableRow({
            children: [
              new TableCell({ children: [new Paragraph(a.task)] }),
              new TableCell({ children: [new Paragraph(a.owner || "—")] }),
              new TableCell({ children: [new Paragraph(a.due_date || "—")] }),
              new TableCell({ children: [new Paragraph(a.priority.toUpperCase())] }),
              new TableCell({ children: [new Paragraph(`${(a.confidence * 100).toFixed(0)}%`)] }),
            ],
          })
      ),
    ];

    children.push(
      new Table({
        rows: actionRows,
        width: { size: 100, type: WidthType.PERCENTAGE },
      })
    );
  }

  // Risks & Blockers
  if (report.risks_blockers.length > 0) {
    children.push(
      new Paragraph({ text: "Risks & Blockers", heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 200 } })
    );
    for (const risk of report.risks_blockers) {
      children.push(
        new Paragraph({ text: risk, bullet: { level: 0 }, spacing: { after: 80 } })
      );
    }
  }

  // Open Questions
  if (report.open_questions.length > 0) {
    children.push(
      new Paragraph({ text: "Open Questions", heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 200 } })
    );
    for (const q of report.open_questions) {
      children.push(
        new Paragraph({ text: q, bullet: { level: 0 }, spacing: { after: 80 } })
      );
    }
  }

  // Follow-up needed
  if (report.follow_up_needed) {
    children.push(
      new Paragraph({
        children: [
          new TextRun({ text: "⚠️ Follow-up meeting recommended", bold: true }),
        ],
        spacing: { before: 400 },
      })
    );
  }

  // Footer
  children.push(
    new Paragraph({
      children: [
        new TextRun({ text: "Generated by KaiNote", italics: true, size: 18, color: "888888" }),
      ],
      spacing: { before: 600 },
      alignment: AlignmentType.CENTER,
    })
  );

  const doc = new Document({
    sections: [{ children }],
  });

  return Packer.toBlob(doc);
}
