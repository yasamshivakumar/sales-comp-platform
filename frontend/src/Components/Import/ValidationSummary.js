import {
  Alert,
  Box,
  Chip,
  Collapse,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useState } from "react";

/**
 * Validation results card for import drawers.
 */
export default function ValidationSummary({ validation }) {
  const [showErrors, setShowErrors] = useState(true);

  if (!validation) {
    return (
      <Typography variant="body2" color="text.secondary">
        Run validation to check rows, duplicates, and required columns before importing.
      </Typography>
    );
  }

  const errorCount = validation.errorCount ?? 0;
  const validRows = validation.validRows ?? 0;
  const totalRows = validation.totalRows ?? 0;
  const missing = validation.missingColumns || [];
  const errors = validation.errors || [];

  return (
    <Box className="imp-card">
      <Typography variant="subtitle2" gutterBottom>
        Validation summary
      </Typography>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
        <Chip size="small" label={`Rows found: ${totalRows}`} />
        <Chip size="small" color="success" label={`✓ Valid: ${validRows}`} />
        <Chip
          size="small"
          color={errorCount > 0 ? "error" : "default"}
          label={`⚠ Invalid: ${errorCount}`}
        />
        {(validation.warningCount || 0) > 0 ? (
          <Chip size="small" color="warning" label={`Warnings: ${validation.warningCount}`} />
        ) : null}
      </Stack>

      {missing.length > 0 ? (
        <Alert severity="warning" sx={{ mb: 1.5 }}>
          Missing required columns: {missing.join(", ")}
        </Alert>
      ) : null}

      {errorCount === 0 ? (
        <Alert severity="success">File looks good — ready to import.</Alert>
      ) : (
        <>
          <Link
            component="button"
            type="button"
            variant="body2"
            underline="hover"
            onClick={() => setShowErrors((v) => !v)}
          >
            {showErrors ? "Hide" : "Show"} validation table ({errors.length})
          </Link>
          <Collapse in={showErrors}>
            <Box className="imp-errors" sx={{ mt: 1 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell width={72}>Row</TableCell>
                    <TableCell>Issue</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {errors.slice(0, 50).map((err, idx) => (
                    <TableRow key={`${err.row}-${idx}`}>
                      <TableCell>{err.row ?? "—"}</TableCell>
                      <TableCell>{err.message}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </Collapse>
        </>
      )}
    </Box>
  );
}
