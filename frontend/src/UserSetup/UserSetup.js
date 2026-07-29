import { Navigate, Route, Routes } from "react-router-dom";
import PeopleCenter from "./PeopleCenter";
import PeopleCreatePage from "./PeopleCreatePage";
import PeopleWorkspace from "./PeopleWorkspace";
import "./people.css";

function UserSetup() {
  return (
    <Routes>
      <Route index element={<PeopleCenter />} />
      <Route path="new" element={<PeopleCreatePage />} />
      <Route path="import" element={<Navigate to="/user-setup?import=1" replace />} />
      <Route path=":personId/*" element={<PeopleWorkspace />} />
      <Route path="*" element={<Navigate to="." replace />} />
    </Routes>
  );
}

export default UserSetup;
