"use client";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";

export default function AdminLayout({ children }) {
  return (
    <>
      <Header />
      <Sidebar />
      {children}
    </>
  );
}


