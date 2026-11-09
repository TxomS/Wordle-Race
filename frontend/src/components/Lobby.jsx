import { useEffect, useState } from "react";

// Shown to the player who created a race, until the opponent joins. The page keeps
// polling in the background, so it turns into the game by itself.
export default function Lobby({ code }) {
  const link = `${window.location.origin}/g/${code}`;
  const [copied, setCopied] = useState(null); // null, "yes" or "no"

  useEffect(() => {
    if (!copied) return undefined;
    const timer = setTimeout(() => setCopied(null), 2500);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied("yes");
    } catch {
      setCopied("no"); // clipboard blocked: the link is shown below to copy by hand
    }
  }

  return (
    <section className="lobby">
      <h1>Waiting for your opponent</h1>
      <p>Share this code, or send them the link:</p>
      <p className="lobby__code" aria-label={`Game code ${code.split("").join(" ")}`}>
        {code}
      </p>
      <p className="lobby__link">{link}</p>
      <button type="button" className="button button--primary" onClick={copyLink}>
        Copy link
      </button>
      <p className="lobby__note" role="status">
        {copied === "yes" && "Link copied."}
        {copied === "no" && "Could not copy. Select the link above and copy it."}
        {copied === null && "The race starts the moment they join."}
      </p>
    </section>
  );
}
