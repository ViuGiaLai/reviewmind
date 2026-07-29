/* ═══════════════════════════════════════════════════════════════════════════════
   Diff Viewer — Side-by-side original vs suggested
   ═══════════════════════════════════════════════════════════════════════════════ */

export function DiffViewer({ original, suggested }: { original: string; suggested: string }) {
  const origLines = original.split("\n");
  const suggLines = suggested.split("\n");

  return (
    <div className="diff-viewer">
      <div className="diff-header">
        <span className="diff-header-original">Original</span>
        <span className="diff-header-suggested">Suggested</span>
      </div>
      <div className="diff-panels">
        <div className="diff-panel original">
          <div className="diff-lines">
            {origLines.map((line, i) => (
              <div key={i} className="diff-line">
                <span className="diff-lineno">{i + 1}</span>
                <span className="diff-text">{line || " "}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="diff-panel suggested">
          <div className="diff-lines">
            {suggLines.map((line, i) => {
              const cls = line !== (origLines[i] || "") ? (i >= origLines.length ? "added" : "changed") : "";
              return (
                <div key={i} className={`diff-line ${cls}`}>
                  <span className="diff-lineno">{i + 1}</span>
                  <span className="diff-text">{line || " "}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
