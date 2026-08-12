/**
 * Decode a base64 string to a Uint8Array.
 * Works in both Node.js and browser environments.
 * @param b64
 * @returns The decoded bytes.
 */
export function base64ToBytes(b64: string): Uint8Array {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
}

/**
 * Encode a Uint8Array to a base64 string.
 * Works in both Node.js and browser environments.
 * @param bytes
 * @returns The base64-encoded string.
 */
export function bytesToBase64(bytes: Uint8Array): string {
    let binary = '';
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary);
}
