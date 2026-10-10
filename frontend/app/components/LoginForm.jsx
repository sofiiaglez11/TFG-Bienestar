import { useState } from 'react';
import { Eye, EyeOff } from "lucide-react";


// export default function LoginForm({ onLogin }) {
//     const [email, setEmail] = useState('');
//     const [password, setPassword] = useState('');

export default function LoginForm({ onLogin, message, loading }) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);


    const handleSubmit = async (e) => {

        e.preventDefault(); // para evitar que la página se recargue al enviar

        await onLogin(email, password);
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
                width: '90%',
                maxWidth: '600px',
                margin: '0 auto'

            }}>


            <label htmlFor="email" style={{ marginBottom: '4px', marginTop: '12px' }}>
                Email:
            </label>
            <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    border: '1px solid var(--border, #cbd5e1)',
                    background: 'var(--bg-input, #f8fafc)',
                    color: 'var(--text-primary, #0f172a)',
                    fontSize: '14px',
                    outline: 'none',
                    boxSizing: 'border-box',
                }}
            />




            <label htmlFor="password" style={{ marginBottom: '4px', marginTop: '12px' }}>
                Contraseña:
            </label>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center', width: '100%' }}>
                <input
                    type={showPassword ? "text" : "password"}
                    id="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    style={{
                        width: '100%',
                        padding: '10px 40px 10px 12px',
                        borderRadius: '8px',
                        border: '1px solid var(--border, #cbd5e1)',
                        background: 'var(--bg-input, #f8fafc)',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '14px',
                        outline: 'none',
                        boxSizing: 'border-box',
                    }}
                />
                <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                        position: 'absolute',
                        right: '10px',
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        padding: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--text-secondary, #64748b)',
                    }}
                    title={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                >
                    {showPassword ? (
                        <EyeOff size={20} strokeWidth={2} />
                    ) : (
                        <Eye size={20} strokeWidth={2} />
                    )}
                </button>
            </div>



            {message && (
                <div style={{
                    marginTop: '14px',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    fontSize: '13px',
                    backgroundColor: message.type === 'error' ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)',
                    color: message.type === 'error' ? '#ef4444' : '#22c55e',
                    border: `1px solid ${message.type === 'error' ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'}`,
                }}>
                    {message.text}
                </div>
            )}

            <button type="submit" style={{ marginTop: '20px' }} disabled={loading}>
                {loading ? 'Cargando...' : 'Login'}
            </button>        </form>


    );
}