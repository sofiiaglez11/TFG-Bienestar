"use client";

import LoginForm from "../components/LoginForm";

const BACKEND_URL = "http://localhost:8000";

export default function LoginPage() {

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
            console.log("Respuesta del servidor:", data);
        } catch (error) {
            console.error("Error al iniciar sesión:", error);
        }
    };



    return (
        <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh'
        }}>
            <LoginForm onLogin={handleLogin} />
        </div>
    );
}