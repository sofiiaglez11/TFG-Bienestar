import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // devIndicators: false,
  // Permite acceder a los recursos de desarrollo desde otros dispositivos en la red local
  allowedDevOrigins: ["192.168.0.144"],
};

export default nextConfig;
