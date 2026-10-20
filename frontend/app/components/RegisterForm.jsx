import { useState } from 'react';
import { GraduationCap, Users } from 'lucide-react';

const inputStyle = {
    width: '100%',
    padding: '10px 12px',
    borderRadius: '8px',
    border: '1px solid var(--border, #cbd5e1)',
    background: 'var(--bg-input, #f8fafc)',
    color: 'var(--text-primary, #0f172a)',
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box',
};

export default function RegisterForm({ onRegister }) {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState('student');

    const handleSubmit = async (e) => {
        e.preventDefault();
        await onRegister(name, email, password, role);
    };

    const roleOptions = [
        {
            value: 'student',
            Icon: GraduationCap,
            label: 'Estudiante',
            desc: 'Accede al chat, estadísticas y cursos en los que estás matriculado',
            color: '#10b981',
        },
        {
            value: 'teacher',
            Icon: Users,
            label: 'Profesor',
            desc: 'Crea y gestiona los cursos que impartes',
            color: '#6366f1',
        },
    ];

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
                gap: '14px',
            }}>

            <label htmlFor="name">Nombre:</label>
            <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                style={inputStyle}
            />

            <label htmlFor="email">Email:</label>
            <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={inputStyle}
            />

            <label htmlFor="password">Contraseña:</label>
            <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={inputStyle}
            />

            {/* Selector de rol */}
            <div>
                <label style={{ display: 'block', marginBottom: '10px', fontSize: '14px', fontWeight: '500' }}>
                    ¿Cómo vas a usar la aplicación?
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                    {roleOptions.map(({ value, Icon, label, desc, color }) => {
                        const selected = role === value;
                        return (
                            <button
                                key={value}
                                type="button"
                                onClick={() => setRole(value)}
                                style={{
                                    padding: '14px 12px',
                                    borderRadius: '10px',
                                    border: selected
                                        ? `2px solid ${color}`
                                        : '2px solid var(--border, #e2e8f0)',
                                    background: selected
                                        ? `color-mix(in srgb, ${color} 10%, transparent)`
                                        : 'var(--bg-input, #f8fafc)',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                    transition: 'all 0.15s ease',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '6px',
                                }}
                            >
                                <Icon size={20} color={selected ? color : 'var(--text-secondary)'} strokeWidth={1.8} />
                                <span style={{
                                    fontWeight: '700',
                                    fontSize: '14px',
                                    color: selected ? color : 'var(--text-primary)',
                                }}>
                                    {label}
                                </span>
                                <span style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                                    {desc}
                                </span>
                            </button>
                        );
                    })}
                </div>
            </div>

            <button type="submit" style={{ marginTop: '4px' }}>Crear cuenta</button>
        </form>
    );
}
