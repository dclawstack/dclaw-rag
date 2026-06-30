"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Copilot } from "@/components/copilot";
import { Sidebar } from "@/components/sidebar";
import { getToken } from "@/lib/auth";
import { API_KEY } from "@/lib/tokens";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  const isLoginRoute = pathname === "/login";

  useEffect(() => {
    // Intentional auth check on mount; localStorage is only readable client-side.
    /* eslint-disable react-hooks/set-state-in-effect */
    if (isLoginRoute) {
      setReady(true);
      return;
    }
    // A logged-in JWT, or the dev API key, grants access.
    if (getToken() || API_KEY) {
      setReady(true);
    } else {
      router.replace("/login");
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [isLoginRoute, pathname, router]);

  // The login page renders bare (no app shell).
  if (isLoginRoute) return <>{children}</>;

  // Avoid flashing the app before the auth check resolves.
  if (!ready) return null;

  return (
    <>
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
      <Copilot />
    </>
  );
}
