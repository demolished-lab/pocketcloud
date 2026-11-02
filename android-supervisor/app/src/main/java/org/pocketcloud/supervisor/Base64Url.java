package org.pocketcloud.supervisor;

/** Minimal RFC 4648 URL-safe, unpadded Base64 codec without Android API-level dependencies. */
public final class Base64Url {
    private static final char[] ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_".toCharArray();
    private Base64Url() {}

    public static byte[] decode(String text) {
        if (text == null || text.isEmpty() || (text.length() & 3) == 1) throw new IllegalArgumentException("Invalid base64url");
        byte[] out = new byte[text.length() * 6 / 8];
        int buffer = 0, bits = 0, index = 0;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            int value = c >= 'A' && c <= 'Z' ? c - 'A' : c >= 'a' && c <= 'z' ? c - 'a' + 26 : c >= '0' && c <= '9' ? c - '0' + 52 : c == '-' ? 62 : c == '_' ? 63 : -1;
            if (value < 0) throw new IllegalArgumentException("Invalid base64url");
            buffer = (buffer << 6) | value;
            bits += 6;
            if (bits >= 8) { bits -= 8; out[index++] = (byte) ((buffer >> bits) & 0xff); }
        }
        if (bits > 0 && (buffer & ((1 << bits) - 1)) != 0) throw new IllegalArgumentException("Noncanonical base64url");
        if (index != out.length || !encode(out).equals(text)) throw new IllegalArgumentException("Noncanonical base64url");
        return out;
    }

    public static String encode(byte[] input) {
        StringBuilder out = new StringBuilder((input.length * 4 + 2) / 3);
        int i = 0;
        while (i + 3 <= input.length) {
            int v = ((input[i] & 255) << 16) | ((input[i + 1] & 255) << 8) | (input[i + 2] & 255);
            out.append(ALPHABET[(v >>> 18) & 63]).append(ALPHABET[(v >>> 12) & 63]).append(ALPHABET[(v >>> 6) & 63]).append(ALPHABET[v & 63]);
            i += 3;
        }
        int remaining = input.length - i;
        if (remaining == 1) {
            int v = (input[i] & 255) << 16;
            out.append(ALPHABET[(v >>> 18) & 63]).append(ALPHABET[(v >>> 12) & 63]);
        } else if (remaining == 2) {
            int v = ((input[i] & 255) << 16) | ((input[i + 1] & 255) << 8);
            out.append(ALPHABET[(v >>> 18) & 63]).append(ALPHABET[(v >>> 12) & 63]).append(ALPHABET[(v >>> 6) & 63]);
        }
        return out.toString();
    }
}
