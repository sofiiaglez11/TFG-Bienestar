import React, { useState, useEffect } from "react";
import { Check, Palette } from "lucide-react";
import { TAG_COLOR_PALETTE } from "../utils/tagUtils";

export default function TagColorPickerModal({ isOpen, onClose, tag, currentColor, onSelectColor }) {
    const [selectedColor, setSelectedColor] = useState(currentColor || null);
    const [saving, setSaving] = useState(false);

    // El componente está siempre montado: hay que resincronizar al abrir otra etiqueta
    useEffect(() => {
        if (isOpen) setSelectedColor(currentColor || null);
    }, [isOpen, tag, currentColor]);

    if (!isOpen || !tag) return null;

    const handleSave = async (colorHex) => {
        setSelectedColor(colorHex);
        setSaving(true);
        try {
            await onSelectColor(tag, colorHex);
            onClose();
        } catch (err) {
            console.error("Error al guardar color de la etiqueta:", err);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(15, 23, 42, 0.5)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999
        }}>
            <div style={{
                backgroundColor: "var(--bg-card, #ffffff)",
                color: "var(--text-primary, #1e293b)",
                borderRadius: "16px",
                padding: "24px",
                maxWidth: "360px",
                width: "90%",
                boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
                border: "1px solid var(--border-color, #e2e8f0)",
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
                    <div style={{
                        padding: "8px",
                        borderRadius: "10px",
                        backgroundColor: "rgba(99, 102, 241, 0.1)",
                        color: "#6366f1"
                    }}>
                        <Palette size={20} />
                    </div>
                    <div>
                        <h3 style={{ margin: 0, fontSize: "16px", fontWeight: "700" }}>Color de Etiqueta</h3>
                        <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary, #64748b)" }}>
                            Personaliza #{tag}
                        </p>
                    </div>
                </div>

                <div style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(5, 1fr)",
                    gap: "12px",
                    margin: "20px 0"
                }}>
                    {TAG_COLOR_PALETTE.map((c) => {
                        const isSelected = selectedColor === c.hex;
                        return (
                            <button
                                key={c.id}
                                onClick={() => handleSave(c.hex)}
                                disabled={saving}
                                title={c.label}
                                style={{
                                    width: "44px",
                                    height: "44px",
                                    borderRadius: "50%",
                                    backgroundColor: c.hex,
                                    border: isSelected ? "3px solid #000" : "2px solid transparent",
                                    boxShadow: isSelected ? "0 0 0 2px #fff, 0 4px 6px -1px rgba(0,0,0,0.1)" : "none",
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    transition: "transform 0.15s ease",
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.transform = "scale(1.1)"}
                                onMouseLeave={(e) => e.currentTarget.style.transform = "scale(1)"}
                            >
                                {isSelected && <Check size={20} color="#ffffff" strokeWidth={3} />}
                            </button>
                        );
                    })}
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "16px" }}>
                    <button
                        onClick={onClose}
                        style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "1px solid var(--border-color, #cbd5e1)",
                            background: "transparent",
                            fontSize: "13px",
                            fontWeight: "600",
                            cursor: "pointer",
                            color: "var(--text-secondary, #475569)"
                        }}
                    >
                        Cancelar
                    </button>
                </div>
            </div>
        </div>
    );
}