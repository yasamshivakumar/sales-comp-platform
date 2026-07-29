import {
  Box,
  Button,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";

/**
 * Final import result panel (drawer step 5).
 */
export default function ImportResult({
  imported = 0,
  skipped = 0,
  failed = 0,
  errors = [],
  onDownloadErrors,
  onDone,
}) {
  const hasErrors = failed > 0 || (errors || []).length > 0;

  return (
    <Box className="imp-result" textAlign="center">
      <CheckCircleIcon
        className="imp-summary__icon"
        color={hasErrors ? "warning" : "success"}
      />
      <Typography variant="h6" sx={{ mt: 1.5, fontWeight: 700 }}>
        {hasErrors ? "Import completed with issues" : "Import successful"}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        Review the totals below. You can download an error report if any rows failed.
      </Typography>

      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        justifyContent="center"
        sx={{ mt: 3 }}
      >
        <Box className="imp-stat">
          <Typography variant="caption" color="text.secondary">
            Imported
          </Typography>
          <Typography variant="h5">{imported}</Typography>
        </Box>
        <Box className="imp-stat">
          <Typography variant="caption" color="text.secondary">
            Skipped
          </Typography>
          <Typography variant="h5">{skipped}</Typography>
        </Box>
        <Box className="imp-stat">
          <Typography variant="caption" color="text.secondary">
            Failed
          </Typography>
          <Typography variant="h5">{failed}</Typography>
        </Box>
      </Stack>

      {hasErrors && (errors || []).length > 0 ? (
        <Box className="imp-errors" sx={{ mt: 2.5, textAlign: "left" }}>
          <Typography variant="subtitle2" gutterBottom>
            Error details
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Row</TableCell>
                <TableCell>Issue</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {errors.slice(0, 25).map((err, idx) => (
                <TableRow key={`${err.row}-${idx}`}>
                  <TableCell>{err.row ?? "—"}</TableCell>
                  <TableCell>{err.message || err.error || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      ) : null}

      <Stack direction="row" spacing={1.5} justifyContent="center" sx={{ mt: 3 }}>
        {hasErrors && onDownloadErrors ? (
          <Button variant="outlined" onClick={onDownloadErrors}>
            Download error report
          </Button>
        ) : null}
        <Button variant="contained" onClick={onDone}>
          Done
        </Button>
      </Stack>
    </Box>
  );
}
