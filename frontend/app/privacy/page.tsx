import Link from "next/link";

export default function PrivacyPage() {
  return (
    <main>
      <section className="card legalCard">
        <p className="legalEyebrow">Privacy Policy</p>
        <h1>Privacy Policy</h1>
        <p className="muted">
          This demo application accepts process documentation inputs and generates draft process documents and exports. This page
          explains what data is handled and how it is retained.
        </p>

        <h2>What We Collect</h2>
        <p>
          The application may process transcript files, audio files, video files, process names, context notes, generated draft
          documents, SIPOC output, and export artifacts.
        </p>

        <h2>How Data Is Used</h2>
        <p>
          Uploaded files and text inputs are used only to analyze the submitted process and generate process documentation outputs,
          including editable drafts and exported files.
        </p>

        <h2>Retention</h2>
        <p>
          Uploaded inputs and generated artifacts are intended to be retained for up to 7 days, after which cleanup and expiration
          routines may remove them.
        </p>

        <h2>Sharing</h2>
        <p>
          Data may be processed by configured AI providers selected for a job, such as Google, OpenAI, Azure OpenAI, or Ollama,
          depending on the active environment configuration.
        </p>

        <h2>Security</h2>
        <p>
          The application uses HTTPS in production and restricts app access with a code-gated session. No system can guarantee
          absolute security, so sensitive data should be uploaded only when appropriate for the deployment environment.
        </p>

        <h2>Contact</h2>
        <p>
          For questions about this deployment, contact the site operator for <strong>demo.kartiksiva.com</strong>.
        </p>

        <p className="muted">
          <Link href="/">Return to App</Link>
        </p>
      </section>
    </main>
  );
}
