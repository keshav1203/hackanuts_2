import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/context/Auth";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";

function Protected({ children }) {
  const { user } = useAuth();
  return user ? children : <Navigate to="/login" replace />;
}

function GuestOnly({ children }) {
  const { user } = useAuth();
  return user ? <Navigate to="/app" replace /> : children;
}

export default function App() {
  return (
    <>
      <div className="bg-pattern" aria-hidden />
      <Routes>
        <Route path="/" element={<Navigate to="/app" replace />} />
        <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
        <Route path="/app" element={<Protected><Dashboard /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
