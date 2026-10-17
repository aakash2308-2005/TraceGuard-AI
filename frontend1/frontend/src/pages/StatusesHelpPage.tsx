import { Card, PageHeader } from "../components/common";
import { StatusChip } from "../components/StatusChip";
import { IconShield } from "../components/icons";

const STATUSES = [
  {
    status: "fact" as const,
    //title: "Fact",
    body: "Independently observed and sourced — for example an on-chain transaction or a registry record. Safe to rely on as ground truth for this case.",
    example: "Wallet 0xabc… sent 2.5 ETH at 14:02 UTC (block 19,204,551).",
  },
  {
    status: "unverified_claim" as const,
    //title: "Unverified claim",
    body: "Reported by a source but not independently corroborated — for example a reputation score or self-reported file metadata. Treat as a lead, not a conclusion.",
    example: "File metadata claims the document was authored by “jsmith”.",
  },
  {
    status: "inference" as const,
   // title: "Inference",
    body: "A reasoned connection drawn from findings — for example a possible wallet association. It is an analytical judgement, not proof.",
    example: "The same username appears in two unrelated phishing pages.",
  },
  {
    status: "hypothesis" as const,
    //title: "Hypothesis",
    body: "A testable explanation for observed facts, not a confirmed conclusion. It should guide further investigation and be accepted only after independent supporting evidence is found.",
    example: "The phisher reuses infrastructure across three campaigns.",
  },
];

export function StatusesHelpPage() {
  return (
    <>
      <PageHeader
        title="Help"
        //subtitle="TraceGuard AI never blurs verified facts with AI inference. Every finding is explicitly labelled — and every label uses text plus an icon, never colour alone."
      />

      <Card
        title="The four labels"
        tone="slate"
        icon={<IconShield size={16} />}
        //subtitle="How to read every finding in the platform."
      >
        <div className="tg-stack">
          {STATUSES.map((s) => (
            <article
              key={s.status}
              style={{
                padding: "var(--tg-space-4)",
                border: "1px solid var(--tg-border)",
                borderRadius: "var(--tg-radius)",
                background: "var(--tg-bg-elev)",
              }}
            >
              <div className="tg-row tg-wrap" style={{ marginBottom: 6 }}>
                <StatusChip status={s.status} />
                
              </div>
              <p className="tg-subtle tg-mb-0">{s.body}</p>
              <p className="tg-hint tg-break">
                <em>Example:</em> {s.example}
              </p>
            </article>
          ))}
        </div>
      </Card>

      
    </>
  );
}
