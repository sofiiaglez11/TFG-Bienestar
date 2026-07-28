import { useState } from 'react';

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

        // console.log("Datos enviaodos:", { email, password });

        // alert("Intentando iniciar sesión con:\nEmail: " + email + "\nPassword: " + password);

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



            {/* <label htmlFor="email">Email:</label>
            <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
            /> */}

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


            {/* <label htmlFor="password">Password:</label>
            <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
            /> */}

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
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                            <line x1="1" y1="1" x2="23" y2="23"></line>
                        </svg>
                    ) : (
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                    )}
                </button>
            </div>



            <button type="submit" style={{ marginTop: '20px' }}>Login</button>
        </form>


    );
}