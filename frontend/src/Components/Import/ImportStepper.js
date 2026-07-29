import { Box, Step, StepLabel, Stepper, Typography } from "@mui/material";

const DEFAULT_STEPS = ["Template", "Upload", "Validate", "Import", "Complete"];

/**
 * Compact enterprise stepper for import drawers.
 */
export default function ImportStepper({
  activeStep = 0,
  steps = DEFAULT_STEPS,
}) {
  return (
    <Box className="imp-stepper" sx={{ px: 0.5, pt: 0.5, pb: 1.5 }}>
      <Stepper activeStep={activeStep} alternativeLabel>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>
              <Typography variant="caption" className="imp-stepper__label">
                {label}
              </Typography>
            </StepLabel>
          </Step>
        ))}
      </Stepper>
    </Box>
  );
}

export { DEFAULT_STEPS };
