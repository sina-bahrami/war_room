import { useState } from "react";

interface LoginPageProps {
  onLogin: (username: string) => void;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Something went wrong");
        return;
      }
      localStorage.setItem("auth", "true");
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("username", data.username);
      onLogin(data.username);
    } catch {
      setError("Could not connect to server");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", height:"100vh", background:"#0f172a", color:"white" }}>
      <h1 style={{ fontSize:"2rem", marginBottom:"0.5rem" }}>Prompcorp Tender Intelligence</h1>
      <p style={{ color:"#94a3b8", marginBottom:"2rem" }}>{mode === "login" ? "Sign in to continue" : "Create a new account"}</p>
      <form onSubmit={handleSubmit} style={{ display:"flex", flexDirection:"column", gap:"1rem", width:"320px" }}>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={e => setUsername(e.target.value)}
          style={{ padding:"0.75rem", borderRadius:"8px", border:"1px solid #334155", background:"#1e293b", color:"white", fontSize:"1rem" }}
        />
        <input
          type="password"
          placeholder={mode === "register" ? "Password (min 6 characters)" : "Password"}
          value={password}
          onChange={e => setPassword(e.target.value)}
          style={{ padding:"0.75rem", borderRadius:"8px", border:"1px solid #334155", background:"#1e293b", color:"white", fontSize:"1rem" }}
        />
        {error && <p style={{ color:"#f87171", margin:0 }}>{error}</p>}
        <button type="submit" disabled={loading} style={{ padding:"0.75rem", borderRadius:"8px", background:"#3b82f6", color:"white", fontSize:"1rem", cursor:"pointer", border:"none", opacity: loading ? 0.7 : 1 }}>
          {loading ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
        </button>
        <button type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
          style={{ padding:"0.75rem", borderRadius:"8px", background:"transparent", color:"#94a3b8", fontSize:"0.9rem", cursor:"pointer", border:"1px solid #334155" }}>
          {mode === "login" ? "Create new account" : "Already have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
