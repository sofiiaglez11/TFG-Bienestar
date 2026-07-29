"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import LoginForm from "../components/LoginForm";

const BACKEND_URL = "http://localhost:8000";


export default function LoginPage() {
    const router = useRouter();
    const [message, setMessage] = useState(null);
    const [loading, setLoading] = useState(false);


    const handleLogin = async (email, password) => {
        setMessage(null);
        setLoading(true);
        try {
            const response = await fetch(`${BACKEND_URL}/api/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });

            if (!response.ok) {
                let errorMsg = "Email o contraseña incorrectos";
                try {
                    const errData = await response.json();
                    if (errData.detail) errorMsg = errData.detail;
                } catch (e) {
                    errorMsg = `Error del servidor (${response.status})`;
                }
                setMessage({ type: 'error', text: errorMsg });
                setLoading(false);
                return;
            }

            const data = await response.json();
            localStorage.setItem("token", data.token);
            if (data.user) {
                localStorage.setItem("userName", data.user.name || "");
                localStorage.setItem("userEmail", data.user.email || "");
            }
            setMessage({ type: 'success', text: "¡Inicio de sesión correcto! Redirigiendo..." });

            // Pausa de 1 segundo para mostrar el mensaje de éxito antes de navegar al chat
            setTimeout(() => {
                router.push("/chat");
            }, 1000);
        } catch (error) {
            console.error("Error al iniciar sesión:", error);
            setMessage({ type: 'error', text: "No se pudo conectar con el servidor" });
            setLoading(false);
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
            <LoginForm
                onLogin={handleLogin}
                message={message}
                loading={loading}
            />
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                ¿No tienes cuenta?{' '}
                <a href="/register" style={{ color: 'var(--brand)' }}>Regístrate</a>
            </p>
        </div>
    );
}