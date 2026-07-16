import { useState } from 'react';

export default function RegisterForm({ onRegister }) {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        await onRegister(name, email, password);
    };

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
                width: '90%',
                maxWidth: '600px',
                margin: '0 auto',
                gap: '8px',
            }}>

            <label htmlFor="name">Nombre:</label>
            <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
            />

            <label htmlFor="email">Email:</label>
            <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
            />

            <label htmlFor="password">Contraseña:</label>
            <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
            />

            <button type="submit" style={{ marginTop: '12px' }}>Crear cuenta</button>
        </form>
    );
}
