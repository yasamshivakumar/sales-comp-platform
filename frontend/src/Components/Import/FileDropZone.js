import { useRef, useState } from "react";
import { Box, Button, Stack, Typography } from "@mui/material";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined";
import "./importDialog.css";

/**
 * Drag-and-drop CSV upload zone for enterprise import dialogs.
 */
export default function FileDropZone({
  file,
  onFileChange,
  accept = ".csv,text/csv",
  maxSizeMb = 10,
  disabled = false,
  hint = "CSV files only",
}) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const pick = (selected) => {
    if (!selected || disabled) return;
    onFileChange?.(selected);
  };

  return (
    <Box
      className={`imp-dropzone${dragOver ? " is-active" : ""}${file ? " has-file" : ""}${
        disabled ? " is-disabled" : ""
      }`}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label={file ? `Selected file ${file.name}. Click to replace.` : "Drop CSV file or browse"}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if (disabled) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        pick(e.dataTransfer.files?.[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        hidden
        disabled={disabled}
        onChange={(e) => {
          pick(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <Box className="imp-dropzone__icon" aria-hidden>
        {file ? <InsertDriveFileOutlinedIcon /> : <CloudUploadOutlinedIcon />}
      </Box>
      <Typography variant="subtitle1" className="imp-dropzone__title">
        {file ? file.name : "Drop CSV here or browse"}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {file
          ? `${(file.size / 1024).toFixed(1)} KB · Click to replace`
          : `${hint} · Max ${maxSizeMb} MB`}
      </Typography>
      <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} justifyContent="center">
        <Button
          size="small"
          variant="outlined"
          disabled={disabled}
          onClick={(e) => {
            e.stopPropagation();
            inputRef.current?.click();
          }}
        >
          Browse file
        </Button>
        {file ? (
          <Button
            size="small"
            color="inherit"
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation();
              onFileChange?.(null);
            }}
          >
            Remove
          </Button>
        ) : null}
      </Stack>
    </Box>
  );
}
