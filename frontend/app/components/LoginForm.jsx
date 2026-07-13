import { useState } from 'react';

export default function LoginForm() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = (e) => {

        e.preventDefault(); // para evitar que la página se recargue al enviar

        console.log("Datos enviaodos:", { email, password });

        alert("Intentando iniciar sesión con:\nEmail: " + email + "\nPassword: " + password);

    }


    return (
        <form onSubmit={handleSubmit}
            style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                padding: '20px',
                color: 'var(--text-primary)',
                display: 'flex',
                flexDirection: 'column',
                width: '300px',
                margin: '0 auto'

            }}>
            <label htmlFor="email">Email:</label>
            <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
            />

            <label htmlFor="password">Password:</label>
            <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
            />

            <button type="submit" style={{ marginTop: '20px' }}>Login</button>
        </form>
    );
}