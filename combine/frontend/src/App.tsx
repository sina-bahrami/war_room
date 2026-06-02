import { useEffect, useState } from "react";

import { AuthScreen } from "./components/AuthScreen";
import { DashboardApp } from "./components/DashboardApp";
import { ApiError, getSession, login, logout, register } from "./lib/api";
import type { AppRoute, AuthenticatedUser, DashboardView, LoginPayload, RegisterPayload } from "./lib/types";

const DASHBOARD_ROUTES: DashboardView[] = ["active", "upcoming", "recently_closed", "sources"];

function getCurrentRoute(): AppRoute {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (hash === "login" || hash === "register") {
    return hash;
  }
  if (DASHBOARD_ROUTES.includes(hash as DashboardView)) {
    return hash as DashboardView;
  }
  return "login";
}

function isDashboardRoute(route: AppRoute): route is DashboardView {
  return DASHBOARD_ROUTES.includes(route as DashboardView);
}

export default function App() {
  const [route, setRoute] = useState<AppRoute>(getCurrentRoute);
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    const handleHashChange = () => {
      setAuthError(null);
      setRoute(getCurrentRoute());
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    async function loadSession() {
      try {
        const session = await getSession();
        setUser(session.user);
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 401)) {
          setAuthError(error instanceof Error ? error.message : "Failed to restore your session.");
        }
      } finally {
        setAuthChecked(true);
      }
    }

    void loadSession();
  }, []);

  useEffect(() => {
    if (!authChecked) {
      return;
    }

    if (!user && isDashboardRoute(route)) {
      window.location.hash = "/login";
      return;
    }

    if (user && !isDashboardRoute(route)) {
      window.location.hash = "/active";
    }
  }, [authChecked, route, user]);

  async function handleLogin(payload: LoginPayload) {
    setAuthBusy(true);
    setAuthError(null);
    try {
      const session = await login(payload);
      setUser(session.user);
      window.location.hash = "/active";
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Sign-in failed.");
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleRegister(payload: RegisterPayload) {
    setAuthBusy(true);
    setAuthError(null);
    try {
      const session = await register(payload);
      setUser(session.user);
      window.location.hash = "/active";
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Account creation failed.");
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleLogout() {
    setAuthBusy(true);
    setAuthError(null);
    try {
      await logout();
      setUser(null);
      window.location.hash = "/login";
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Sign-out failed.");
    } finally {
      setAuthBusy(false);
    }
  }

  if (!authChecked) {
    return <div className="status-screen">Checking session...</div>;
  }

  if (!user) {
    return (
      <AuthScreen
        mode={route === "register" ? "register" : "login"}
        busy={authBusy}
        error={authError}
        onLogin={handleLogin}
        onRegister={handleRegister}
        onSwitchMode={(mode) => {
          setAuthError(null);
          window.location.hash = `/${mode}`;
        }}
      />
    );
  }

  const dashboardView = isDashboardRoute(route) ? route : "active";

  return (
    <DashboardApp
      user={user}
      view={dashboardView}
      onChangeView={(view) => {
        setAuthError(null);
        window.location.hash = `/${view}`;
      }}
      onLogout={handleLogout}
    />
  );
}
