import ReportLibrary from "./ReportLibrary";

/** Owned reports only — same library UI with mine=1. */
function SavedReports() {
  return <ReportLibrary mode="saved" />;
}

export default SavedReports;
