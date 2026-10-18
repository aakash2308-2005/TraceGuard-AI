import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createUser, getConfig, listUsers } from "../api/endpoints";
import { toApiError } from "../api/client";
import { toast } from "../state/toast";
import {
  Banner,
  Button,
  Card,
  DataTable,
  ErrorBanner,
  Field,
  Loading,
  PageHeader,
  Pill,
} from "../components/common";
import { IconLayers, IconPlus, IconShield, IconUsers } from "../components/icons";
import { titleCase } from "../utils/format";

const ROLES = ["admin", "lead_investigator", "investigator", "reviewer", "readonly"];

const ROLE_NOTES: Record<string, string> = {
  admin: "Full control, including user management and configuration.",
  lead_investigator: "Owns cases, assigns members, and starts investigations.",
  investigator: "Adds evidence and runs investigations on assigned cases.",
  reviewer: "Reviews and approves generated reports.",
  readonly: "View-only access to assigned cases.",
};

export function AdminPage() {
  const qc = useQueryClient();
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const configQuery = useQuery({ queryKey: ["config"], queryFn: getConfig });

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("investigator");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => createUser(username, email, password, role),
    onSuccess: () => {
      const created = username.trim();
      setUsername("");
      setEmail("");
      setPassword("");
      setError(null);
      void qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("User created", `${created} · ${titleCase(role)}`);
    },
    onError: (err) => {
      const message = toApiError(err).message;
      setError(message);
      toast.error("Could not create user", message);
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    mutation.mutate();
  };

  return (
    <>
      <PageHeader
        title="Administration"
        //subtitle="Manage operator accounts and inspect the runtime configuration."
        actions={
          <span className="tg-pill tg-pill-info">
            {usersQuery.data ? `${usersQuery.data.length} user${usersQuery.data.length === 1 ? "" : "s"}` : "…"}
          </span>
        }
      />

      <div className="tg-grid tg-grid-3">
        <div className="tg-span-2">
          <Card
            title="Users"
            tone="violet"
            icon={<IconUsers size={16} />}
            //subtitle="Roles determine what each operator can do within a case."
            bodyClassName="tg-flush"
          >
            {usersQuery.isLoading && (
              <div style={{ padding: "var(--tg-space-6)" }}>
                <Loading label="Loading users…" />
              </div>
            )}
            {usersQuery.isError && (
              <div style={{ padding: "var(--tg-space-6)" }}>
                <ErrorBanner message="Could not load users." />
              </div>
            )}
            {usersQuery.data && (
              <DataTable
                columns={["Username", "Email", "Role", "Status"]}
                rows={usersQuery.data.map((u) => [
                  <span key={`${u.id}-u`} className="tg-list-title">
                    {u.username}
                  </span>,
                  <span key={`${u.id}-e`} className="tg-dim">
                    {u.email}
                  </span>,
                  titleCase(u.role),
                  <Pill key={`${u.id}-s`} tone={u.is_active ? "success" : "neutral"}>
                    {u.is_active ? "Active" : "Disabled"}
                  </Pill>,
                ])}
              />
            )}
          </Card>

          <Card
            title="Runtime configuration"
            tone="blue"
            icon={<IconLayers size={16} />}
            subtitle="Operational modes currently in effect."
            bodyClassName="tg-flush"
          >
            {configQuery.isLoading && (
              <div style={{ padding: "var(--tg-space-6)" }}>
                <Loading label="Loading configuration…" />
              </div>
            )}
            {configQuery.isError && (
              <div style={{ padding: "var(--tg-space-6)" }}>
                <ErrorBanner message="Could not load configuration." />
              </div>
            )}
            {configQuery.data && (
              <DataTable
                columns={["Setting", "Value"]}
                rows={Object.entries(configQuery.data).map(([k, v]) => [
                  <span key={k} className="tg-break">
                    {k.replace(/_/g, " ")}
                  </span>,
                  <span key={`${k}-v`} className="tg-break">
                    {String(v)}
                  </span>,
                ])}
              />
            )}
          </Card>
        </div>

        <div>
          <Card title="Create user" tone="cyan" icon={<IconPlus size={16} />}>
            <form onSubmit={onSubmit}>
              <Field label="Username" htmlFor="username">
                <input
                  id="username"
                  className="tg-input"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="off"
                  required
                />
              </Field>
              <Field label="Email" htmlFor="email">
                <input
                  id="email"
                  className="tg-input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="off"
                  required
                />
              </Field>
              <Field
                label="Password"
                htmlFor="password"
                hint="Minimum 8 characters."
              >
                <input
                  id="password"
                  className="tg-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                />
              </Field>
              <Field label="Role" htmlFor="role" hint={ROLE_NOTES[role]}>
                <select
                  id="role"
                  className="tg-select"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {titleCase(r)}
                    </option>
                  ))}
                </select>
              </Field>

              {error && <Banner tone="error">{error}</Banner>}

              <Button
                type="submit"
                variant="primary"
                fullWidth
                disabled={mutation.isPending}
                icon={<IconPlus size={16} />}
              >
                {mutation.isPending ? "Creating…" : "Create user"}
              </Button>
            </form>
          </Card>

          <Card title="Role reference" tone="slate" icon={<IconShield size={16} />}>
            <ul className="tg-list">
              {ROLES.map((r) => (
                <li key={r} className="tg-list-item">
                  <div className="tg-list-title">{titleCase(r)}</div>
                  <div className="tg-list-meta">{ROLE_NOTES[r]}</div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
