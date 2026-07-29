import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Divider,
  Drawer,
  IconButton,
  Skeleton,
  Stack,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import { useNavigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../../api";
import { useToast } from "../../Components/Toast";
import {
  CompensationPlanChip,
  EmployeeAvatar,
  EmptyValue,
  RoleChip,
  SoftChip,
  StatusChip,
} from "./peopleCells";

const DRAWER_TABS = [
  { id: "overview", label: "Overview" },
  { id: "organization", label: "Organization" },
  { id: "compensation", label: "Compensation" },
  { id: "quota", label: "Quota & Attainment" },
  { id: "rules", label: "Commission Rules" },
  { id: "history", label: "Commission History" },
  { id: "transactions", label: "Transactions" },
  { id: "orders", label: "Orders" },
  { id: "access", label: "Access" },
  { id: "audit", label: "Audit Log" },
];

function Field({ label, children }) {
  return (
    <Box className="pe-drawer-field">
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Box sx={{ mt: 0.35 }}>{children}</Box>
    </Box>
  );
}

/**
 * Right-side employee preview drawer. Full profile remains at /user-setup/:id.
 */
export default function EmployeeDrawer({ personId, open, onClose }) {
  const navigate = useNavigate();
  const { error } = useToast();
  const [person, setPerson] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("overview");
  const [rules, setRules] = useState([]);

  useEffect(() => {
    if (!open || !personId) {
      setPerson(null);
      setRules([]);
      setTab("overview");
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const [personRes, rulesRes] = await Promise.all([
          api.get(`user-setup/${personId}/`),
          api.get(`user-setup/${personId}/commission-rules/`).catch(() => ({ data: {} })),
        ]);
        if (cancelled) return;
        setPerson(personRes.data);
        const rows = Array.isArray(rulesRes.data?.results)
          ? rulesRes.data.results
          : Array.isArray(rulesRes.data)
            ? rulesRes.data
            : [];
        setRules(rows);
      } catch (err) {
        if (!cancelled) {
          error(getApiErrorMessage(err, "Failed to load employee"));
          onClose?.();
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, personId, error, onClose]);

  const goFull = (section = "overview") => {
    onClose?.();
    navigate(`/user-setup/${personId}/${section}`);
  };

  const pc = person?.participant_compensation || {};
  const name = person?.display_name || person?.name || "Employee";

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      className="pe-employee-drawer-root"
      PaperProps={{
        className: "pe-employee-drawer",
        sx: { width: { xs: "100%", sm: 560, md: 640 }, maxWidth: "100vw" },
      }}
    >
      <Box className="pe-employee-drawer__header">
        {loading || !person ? (
          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ flex: 1 }}>
            <Skeleton variant="circular" width={48} height={48} />
            <Box sx={{ flex: 1 }}>
              <Skeleton width="60%" />
              <Skeleton width="40%" />
            </Box>
          </Stack>
        ) : (
          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ flex: 1, minWidth: 0 }}>
            <EmployeeAvatar person={person} size={48} />
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h6" fontWeight={700} noWrap>
                {name}
              </Typography>
              <Typography variant="body2" color="text.secondary" noWrap>
                {[person.employee_id, person.email].filter(Boolean).join(" · ") || "—"}
              </Typography>
              <Stack direction="row" spacing={0.75} sx={{ mt: 0.75 }} flexWrap="wrap" useFlexGap>
                <StatusChip code={person.status} label={person.status_label} />
                <RoleChip role={person.role} />
              </Stack>
            </Box>
          </Stack>
        )}
        <Stack direction="row" spacing={0.5}>
          <IconButton
            aria-label="Open full profile"
            size="small"
            onClick={() => goFull("overview")}
            disabled={!personId}
          >
            <OpenInNewIcon fontSize="small" />
          </IconButton>
          <IconButton aria-label="Close" size="small" onClick={onClose}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Stack>
      </Box>

      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        variant="scrollable"
        scrollButtons="auto"
        className="pe-employee-drawer__tabs"
      >
        {DRAWER_TABS.map((t) => (
          <Tab key={t.id} value={t.id} label={t.label} />
        ))}
      </Tabs>

      <Box className="pe-employee-drawer__body">
        {loading || !person ? (
          <Stack spacing={1.5}>
            <Skeleton height={28} />
            <Skeleton height={28} />
            <Skeleton height={80} />
          </Stack>
        ) : (
          <>
            {tab === "overview" ? (
              <Stack spacing={2}>
                <Box className="pe-drawer-card">
                  <Typography variant="subtitle2" gutterBottom>
                    Snapshot
                  </Typography>
                  <div className="pe-drawer-grid">
                    <Field label="Compensation plan">
                      <CompensationPlanChip
                        plan={person.compensation_plan || person.assigned_plan_name || pc.assigned_plan_name}
                      />
                    </Field>
                    <Field label="Quota">
                      {person.quota_display || person.quota ? (
                        <strong>{person.quota_display || person.quota}</strong>
                      ) : (
                        <EmptyValue label="No quota" />
                      )}
                    </Field>
                    <Field label="Territory">
                      <SoftChip value={person.territory_name} empty="No territory" />
                    </Field>
                    <Field label="Manager">
                      {person.manager_name ? (
                        <strong>{person.manager_name}</strong>
                      ) : (
                        <EmptyValue label="No manager" />
                      )}
                    </Field>
                  </div>
                </Box>
                <Button variant="contained" onClick={() => goFull("overview")}>
                  Open full profile
                </Button>
              </Stack>
            ) : null}

            {tab === "organization" ? (
              <Box className="pe-drawer-card">
                <div className="pe-drawer-grid">
                  <Field label="Department">
                    <SoftChip value={person.department} empty="No department" />
                  </Field>
                  <Field label="Business unit">
                    <SoftChip
                      value={person.business_unit || person.business_group}
                      empty="No business unit"
                    />
                  </Field>
                  <Field label="Region">
                    <SoftChip value={person.region} empty="No region" />
                  </Field>
                  <Field label="Position">
                    <SoftChip value={person.position || person.position_title} empty="No position" />
                  </Field>
                  <Field label="Manager">
                    {person.manager_name || <EmptyValue label="No manager" />}
                  </Field>
                </div>
                <Button sx={{ mt: 2 }} onClick={() => goFull("organization")}>
                  Edit organization
                </Button>
              </Box>
            ) : null}

            {tab === "compensation" ? (
              <Stack spacing={2}>
                <Box className="pe-drawer-card">
                  <Field label="Plan">
                    <CompensationPlanChip
                      plan={person.compensation_plan || person.assigned_plan_name}
                    />
                  </Field>
                  <Field label="Quota">
                    {person.quota_display || <EmptyValue label="No quota" />}
                  </Field>
                  <Divider sx={{ my: 1.5 }} />
                  <Typography variant="subtitle2" gutterBottom>
                    Commission rules
                  </Typography>
                  {rules.length === 0 ? (
                    <EmptyValue label="No commission rules assigned" />
                  ) : (
                    <ul className="pe-drawer-rules">
                      {rules.slice(0, 8).map((rule) => (
                        <li key={rule.id}>
                          <strong>{rule.name}</strong>
                          <span>
                            {rule.compensation_plan_name || "—"}
                            {rule.status ? ` · ${rule.status}` : ""}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Box>
                <Button variant="outlined" onClick={() => goFull("compensation")}>
                  Open compensation
                </Button>
              </Stack>
            ) : null}

            {tab === "access" ? (
              <Box className="pe-drawer-card">
                <Field label="Status">
                  <StatusChip code={person.status} label={person.status_label} />
                </Field>
                <Field label="Login enabled">
                  {person.enable_login ? "Yes" : "No"}
                </Field>
                <Field label="Role">
                  <RoleChip role={person.role} />
                </Field>
                <Button sx={{ mt: 2 }} onClick={() => goFull("access")}>
                  Manage access
                </Button>
              </Box>
            ) : null}

            {["quota", "rules", "history", "transactions", "orders", "audit"].includes(tab) ? (
              <Box className="pe-drawer-card">
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  Open the full profile section for detailed {DRAWER_TABS.find((t) => t.id === tab)?.label?.toLowerCase()} data while keeping this directory open.
                </Typography>
                {tab === "rules" && rules.length > 0 ? (
                  <ul className="pe-drawer-rules" style={{ marginBottom: 16 }}>
                    {rules.slice(0, 6).map((rule) => (
                      <li key={rule.id}>
                        <strong>{rule.name}</strong>
                        <span>
                          {rule.compensation_plan_name || "—"}
                          {rule.status ? ` · ${rule.status}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <Button
                  variant="contained"
                  onClick={() =>
                    goFull(
                      tab === "rules"
                        ? "compensation"
                        : tab === "history"
                          ? "commissions"
                          : tab === "orders"
                            ? "transactions"
                            : tab === "audit"
                              ? "access"
                              : tab
                    )
                  }
                >
                  Open {DRAWER_TABS.find((t) => t.id === tab)?.label}
                </Button>
              </Box>
            ) : null}
          </>
        )}
      </Box>
    </Drawer>
  );
}
