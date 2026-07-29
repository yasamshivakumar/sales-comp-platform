import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  Drawer,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DropZone from "./DropZone";
import ImportProgress from "./ImportProgress";
import ImportResult from "./ImportResult";
import ImportStepper, { DEFAULT_STEPS } from "./ImportStepper";
import ValidationSummary from "./ValidationSummary";
import "./importDialog.css";

/**
 * Enterprise right-side import drawer (Salesforce / Dynamics style).
 *
 * Same config contract as the previous ImportDialog — validate/import adapters
 * only; no CSV parsing changes.
 *
 * Steps: Template → Upload → Validate → Import → Complete
 */
export default function ImportDrawer({ open, onClose, config, onImported }) {
  const [step, setStep] = useState(0);
  const [file, setFile] = useState(null);
  const [phase, setPhase] = useState("idle"); // idle | validating | importing
  const [validation, setValidation] = useState(null);
  const [result, setResult] = useState(null);
  const [localError, setLocalError] = useState("");
  const [showColumns, setShowColumns] = useState(false);

  const maxMb = config?.maxSizeMb ?? 10;
  const requiredColumns = config?.requiredColumns || [];
  const busy = phase === "validating" || phase === "importing";

  const reset = useCallback(() => {
    setStep(0);
    setFile(null);
    setPhase("idle");
    setValidation(null);
    setResult(null);
    setLocalError("");
    setShowColumns(false);
  }, []);

  useEffect(() => {
    if (!open) reset();
  }, [open, reset]);

  const handleClose = () => {
    if (busy) return;
    onClose?.();
  };

  const handleFileChange = (selected) => {
    setLocalError("");
    setValidation(null);
    setResult(null);
    if (!selected) {
      setFile(null);
      return;
    }
    const name = (selected.name || "").toLowerCase();
    if (!name.endsWith(".csv")) {
      setLocalError("Please select a CSV file.");
      setFile(null);
      return;
    }
    if (selected.size > maxMb * 1024 * 1024) {
      setLocalError(`CSV imports are limited to ${maxMb} MB.`);
      setFile(null);
      return;
    }
    setFile(selected);
    setStep(1);
  };

  const handleValidate = async () => {
    if (!file || !config?.validateFile) return;
    setLocalError("");
    setPhase("validating");
    setStep(2);
    try {
      const raw = await config.validateFile(file);
      const normalized = config.normalizeValidation
        ? config.normalizeValidation(raw)
        : raw;
      setValidation(normalized);
      setPhase("idle");
    } catch (err) {
      setLocalError(
        err?.response?.data?.error ||
          err?.message ||
          "Validation failed. Check the file and try again."
      );
      setValidation(null);
      setPhase("idle");
    }
  };

  const handleImport = async () => {
    if (!file || !config?.importFile) return;
    if (validation && (validation.errorCount || 0) > 0) {
      setLocalError("Fix validation errors before importing.");
      return;
    }
    setLocalError("");
    setPhase("importing");
    setStep(3);
    try {
      const raw = await config.importFile(file);
      const normalized = config.normalizeResult
        ? config.normalizeResult(raw)
        : raw;
      setResult(normalized);
      setPhase("idle");
      setStep(4);
      onImported?.(normalized);
    } catch (err) {
      setLocalError(
        err?.response?.data?.error ||
          err?.message ||
          "Import failed. Please try again."
      );
      setPhase("idle");
      setStep(2);
    }
  };

  const downloadErrorReport = () => {
    const rows = result?.errors || validation?.errors || [];
    const lines = [
      "row,message",
      ...rows.map(
        (e) =>
          `${e.row ?? ""},"${String(e.message || e.error || "").replace(/"/g, '""')}"`
      ),
    ];
    const blob = new Blob([lines.join("\n")], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(config?.title || "import")
      .toLowerCase()
      .replace(/\s+/g, "-")}-errors.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const canContinueFromUpload = Boolean(file);
  const canImport =
    Boolean(file) &&
    Boolean(validation) &&
    (validation.errorCount || 0) === 0 &&
    !busy;

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={handleClose}
      className="imp-drawer-root"
      ModalProps={{ keepMounted: false }}
      PaperProps={{
        className: "imp-drawer",
        sx: {
          width: { xs: "100%", sm: 560, md: 620 },
          maxWidth: "100vw",
        },
      }}
    >
      <Box className="imp-drawer__header">
        <Box sx={{ pr: 1, minWidth: 0 }}>
          <Typography variant="h6" fontWeight={700} noWrap>
            {config?.title || "Import"}
          </Typography>
          {config?.description ? (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.35 }}>
              {config.description}
            </Typography>
          ) : null}
        </Box>
        <IconButton
          aria-label="Close import panel"
          onClick={handleClose}
          disabled={busy}
          edge="end"
          size="small"
        >
          <CloseIcon />
        </IconButton>
      </Box>

      <ImportStepper activeStep={step} steps={DEFAULT_STEPS} />

      <Box className="imp-drawer__body">
        {busy ? (
          <ImportProgress phase={phase} />
        ) : step === 4 && result ? (
          <ImportResult
            imported={result.imported}
            skipped={result.skipped}
            failed={result.failed}
            errors={result.errors}
            onDownloadErrors={downloadErrorReport}
            onDone={handleClose}
          />
        ) : (
          <Stack spacing={2.5}>
            {localError ? <Alert severity="error">{localError}</Alert> : null}

            {/* Step 1 — Template */}
            <Box className={`imp-card${step === 0 ? " is-focus" : ""}`}>
              <Typography variant="overline" color="text.secondary">
                Step 1 · Template
              </Typography>
                <Typography variant="subtitle1" fontWeight={600} sx={{ mt: 0.25 }}>
                Download template
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75, mb: 1.5 }}>
                Start from the official CSV so column names match validation. Optional columns
                can stay blank.
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {config?.templateUrl ? (
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<DownloadOutlinedIcon />}
                    href={config.templateUrl}
                    download
                    component="a"
                  >
                    {config.templateLabel || "Download template"}
                  </Button>
                ) : null}
                {requiredColumns.length ? (
                  <Button
                    size="small"
                    color="inherit"
                    endIcon={showColumns ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                    onClick={() => setShowColumns((v) => !v)}
                  >
                    Required columns
                  </Button>
                ) : null}
              </Stack>
              <Collapse in={showColumns}>
                <Stack direction="row" flexWrap="wrap" gap={0.75} sx={{ mt: 1.25 }}>
                  {requiredColumns.map((col) => (
                    <Chip key={col} size="small" label={col} variant="outlined" />
                  ))}
                </Stack>
              </Collapse>
            </Box>

            {/* Step 2 — Upload */}
            <Box className={`imp-card${step === 1 ? " is-focus" : ""}`}>
              <Typography variant="overline" color="text.secondary">
                Step 2 · Upload
              </Typography>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mt: 0.25, mb: 1.25 }}>
                Upload file
              </Typography>
              <DropZone
                file={file}
                onFileChange={handleFileChange}
                maxSizeMb={maxMb}
                hint="Supported format: CSV"
                disabled={busy}
              />
            </Box>

            {/* Step 3 — Validate */}
            <Box className={`imp-card${step === 2 ? " is-focus" : ""}`}>
              <Typography variant="overline" color="text.secondary">
                Step 3 · Validate
              </Typography>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mt: 0.25, mb: 1.25 }}>
                Validate file
              </Typography>
              <ValidationSummary validation={validation} />
            </Box>

            {/* Step 4 teaser */}
            {step < 4 ? (
              <Box className={`imp-card${step === 3 ? " is-focus" : ""}`}>
                <Typography variant="overline" color="text.secondary">
                  Step 4 · Import
                </Typography>
                <Typography variant="subtitle1" fontWeight={600} sx={{ mt: 0.25 }}>
                  Import records
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                  {canImport
                    ? "Validation passed. Click Import in the footer to load records."
                    : "Validate a clean file before importing. Invalid rows must be fixed or removed."}
                </Typography>
              </Box>
            ) : null}
          </Stack>
        )}
      </Box>

      {step !== 4 && !busy ? (
        <Box className="imp-drawer__footer">
          <Button onClick={handleClose} color="inherit" disabled={busy}>
            Cancel
          </Button>
          <Box sx={{ flex: 1 }} />
          {step > 0 && step < 3 ? (
            <Button color="inherit" onClick={() => setStep((s) => Math.max(0, s - 1))}>
              Back
            </Button>
          ) : null}
          {step === 0 ? (
            <Button variant="contained" onClick={() => setStep(1)}>
              Continue
            </Button>
          ) : null}
          {step === 1 ? (
            <>
              <Button
                variant="outlined"
                disabled={!canContinueFromUpload}
                onClick={handleValidate}
              >
                Validate
              </Button>
              <Button
                variant="contained"
                disabled={!canContinueFromUpload}
                onClick={() => setStep(2)}
              >
                Continue
              </Button>
            </>
          ) : null}
          {step === 2 ? (
            <>
              <Button
                variant="outlined"
                disabled={!file}
                onClick={handleValidate}
              >
                {validation ? "Re-validate" : "Validate"}
              </Button>
              <Button
                variant="contained"
                disabled={!canImport}
                onClick={handleImport}
              >
                Import
              </Button>
            </>
          ) : null}
          {step === 3 ? (
            <Button variant="contained" disabled={!canImport} onClick={handleImport}>
              Import
            </Button>
          ) : null}
        </Box>
      ) : null}
    </Drawer>
  );
}
