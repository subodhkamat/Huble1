import "./Auth.css";

export default function Login({ apiUrl, error = "", onDismiss }) {
  function startGoogleLogin() {
    window.location.assign(`${apiUrl}/auth/google`);
  }

  return (
    <main className="auth-screen">
      <div className="auth-glow auth-glow-one" />
      <div className="auth-glow auth-glow-two" />
      <nav className="auth-nav"><a className="auth-brand" href="/"><span className="auth-orb">✳</span><span>BuildAI</span></a><span className="auth-nav-status"><span /> AI workspace</span></nav>
      <section className="auth-layout">
        <div className="auth-copy">
          <div className="auth-badge"><span className="auth-badge-spark">✦</span> YOUR IDEAS, BUILT WITH AI</div>
          <h1>From idea to<br /><span>application.</span></h1>
          <p className="auth-copy-description">Describe what you want to build. Let AI help you generate, edit, test, debug, and preview your next project.</p>
          <div className="auth-feature-list">
            <div className="auth-feature"><span className="auth-feature-icon">✧</span><div><strong>Build from a prompt</strong><small>Turn your idea into a working project.</small></div></div>
            <div className="auth-feature"><span className="auth-feature-icon">⌘</span><div><strong>Iterate with AI</strong><small>Edit, debug, and improve your code.</small></div></div>
            <div className="auth-feature"><span className="auth-feature-icon">◉</span><div><strong>Preview as you go</strong><small>Run your app and inspect the result.</small></div></div>
          </div>
          <div className="auth-footnote"><span className="auth-secure-icon">◇</span> Secure sign-in powered by Google OAuth</div>
        </div>
        <section className="auth-card">
          <div className="auth-card-mark">✳</div>
          <p className="auth-eyebrow">WELCOME TO BUILDAI</p>
          <h2>Sign in to your workspace</h2>
          <p className="auth-subtitle">Use your Google account to continue building.</p>
          {error && <div className="auth-alert" role="alert" onClick={onDismiss}>{error}</div>}
          <button className="google-button" onClick={startGoogleLogin}><svg aria-hidden="true" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5Z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.76 7.18l7.73 6C44.42 38.01 46.98 31.89 46.98 24.55Z"/><path fill="#FBBC05" d="M10.53 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.27-3.13.76-4.59l-7.98-6.19A23.9 23.9 0 0 0 0 24c0 3.87.93 7.53 2.56 10.78l7.97-6.19Z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.91-5.8l-7.73-6c-2.14 1.45-4.89 2.3-8.18 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48Z"/></svg>Continue with Google <span>→</span></button>
          <div className="auth-divider"><span /> <small>QUICK & SECURE</small> <span /></div>
          <div className="auth-trust"><span>✓</span><p><strong>Your workspace, your projects</strong><br />Sign in to access your BuildAI workspace.</p></div>
          <p className="auth-terms">By continuing, you agree to use BuildAI responsibly. Your authentication is handled securely by Google.</p>
        </section>
      </section>
      <footer className="auth-footer"><span>© {new Date().getFullYear()} BuildAI</span><span>Made for builders <b>✦</b></span></footer>
    </main>
  );
}
