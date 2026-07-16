"use client";

import { useRouter } from "next/navigation";
import LoginForm from "../components/LoginForm";

const BACKEND_URL = "http://localhost:8000";


export default function LoginPage() {
    const router = useRouter(); // para navegar a otra página

    const handleLogin = async (email, password) => {
        try {
            const response = await fetch(`${BACKEND_URL}/api/login`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ email, password }),
            });

            if (!response.ok) {
                throw new Error(`Error del servidor: ${response.status}`);
            }

            const data = await response.json();
            localStorage.setItem("token", data.token); // guardar el token en localStorage
            router.push("/chat"); // navegar a la página de chat
            console.log("Respuesta del servidor:", data);
        } catch (error) {
            console.error("Error al iniciar sesión:", error);
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
            <h1 style={{ color: 'var(--text-primary)', marginBottom: '8px' }}>Iniciar sesión</h1>
            <LoginForm onLogin={handleLogin} />
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                ¿No tienes cuenta?{' '}
                <a href="/register" style={{ color: 'var(--brand)' }}>Regístrate</a>
            </p>
        </div>
    );
}