"use client";

import { useRouter } from "next/navigation";
import RegisterForm from "../components/RegisterForm";

const BACKEND_URL = "http://localhost:8000";

export default function RegisterPage() {
    const router = useRouter();

    const handleRegister = async (name, email, password) => {
        try {
            const response = await fetch(`${BACKEND_URL}/api/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, email, password }),
            });

            if (!response.ok) {
                const err = await response.json();
                alert(err.detail || "Error al registrarse");
                return;
            }

            alert("Cuenta creada correctamente. ¡Ya puedes iniciar sesión!");
            router.push("/login");

        } catch (error) {
            console.error("Error al registrarse:", error);
            alert("No se pudo conectar con el servidor");
        }
    };

    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh',
            gap: '16px',
        }}>
            <h1 style={{ color: 'var(--text-primary)', marginBottom: '8px' }}>Crear cuenta</h1>
            <RegisterForm onRegister={handleRegister} />
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                ¿Ya tienes cuenta?{' '}
                <a href="/login" style={{ color: 'var(--brand)' }}>Inicia sesión</a>
            </p>
        </div>
    );
}
