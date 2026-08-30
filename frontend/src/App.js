import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Wall from "@/pages/Wall";
import Take from "@/pages/Take";
import Permalink from "@/pages/Permalink";
import Fallen from "@/pages/Fallen";
import Admin from "@/pages/Admin";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Wall />} />
        <Route path="/take" element={<Take />} />
        <Route path="/m/:id" element={<Permalink />} />
        <Route path="/fallen" element={<Fallen />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
