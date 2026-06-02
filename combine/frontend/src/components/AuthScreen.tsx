import { useEffect, useState, type FormEvent } from "react";

import type { LoginPayload, RegisterPayload } from "../lib/types";

interface AuthScreenProps {
  mode: "login" | "register";
  busy: boolean;
  error: string | null;
  onLogin: (payload: LoginPayload) => Promise<void>;
  onRegister: (payload: RegisterPayload) => Promise<void>;
  onSwitchMode: (mode: "login" | "register") => void;
}

export function AuthScreen({
  mode,
  busy,
  error,
  onLogin,
  onRegister,
  onSwitchMode,
}: AuthScreenProps) {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  useEffect(() => {
    setPassword("");
  }, [mode]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === "login") {
      await onLogin({ identifier, password });
      return;
    }
    await onRegister({ name, email, password });
  }

  return (
    <div className="auth-layout">
      <div className="auth-card">
        <div className="auth-card__brand">
          <h1>Prompcorp Tender Intelligence</h1>
          <p>{mode === "login" ? "Sign in to continue" : "Create a new user account"}</p>
        </div>

        <form className="auth-form" onSubmit={(event) => void handleSubmit(event)}>
          {mode === "register" && (
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Full name"
              autoComplete="name"
              required
            />
          )}

          {mode === "login" ? (
            <input
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
              placeholder="Email or admin user"
              autoComplete="username"
              required
            />
          ) : (
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="Email address"
              type="email"
              autoComplete="email"
              required
            />
          )}

          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
          />

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="auth-button auth-button--primary" disabled={busy}>
            {busy ? (mode === "login" ? "Signing in..." : "Creating account...") : mode === "login" ? "Sign In" : "Create Account"}
          </button>

          <button
            type="button"
            className="auth-button auth-button--secondary"
            onClick={() => onSwitchMode(mode === "login" ? "register" : "login")}
            disabled={busy}
          >
            {mode === "login" ? "Create new account" : "Back to sign in"}
          </button>
        </form>

        <p className="auth-hint">
          Default admin login: <strong>admin</strong> / <strong>admin</strong>. User accounts sign in with email, and duplicate emails are blocked.
        </p>
      </div>
    </div>
  );
}
