package org.pocketcloud.supervisor;

import java.security.MessageDigest;
import java.util.Locale;

public final class PairingProtocol {
    private PairingProtocol() {}

    public static byte[] transcript(String pairingId, String laptopId, String phoneId, String phoneName, String publicKeySha256Hex, String nonce, long expiresAt) {
        String value = "pocketcloud-pair-v1\n" + pairingId + "\n" + laptopId + "\n" + phoneId + "\n" + phoneName + "\n" + publicKeySha256Hex + "\n" + nonce + "\n" + expiresAt + "\n";
        return value.getBytes(java.nio.charset.StandardCharsets.UTF_8);
    }

    public static byte[] sha256(byte[] value) {
        try { return MessageDigest.getInstance("SHA-256").digest(value); }
        catch (Exception e) { throw new IllegalStateException("SHA-256 unavailable", e); }
    }

    public static String hex(byte[] value) {
        StringBuilder out = new StringBuilder(value.length * 2);
        for (byte b : value) out.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        return out.toString();
    }

    public static String colonHex(byte[] value) {
        StringBuilder out = new StringBuilder(value.length * 3);
        for (int i = 0; i < value.length; i++) {
            if (i > 0) out.append(':');
            out.append(String.format(Locale.ROOT, "%02X", value[i] & 0xff));
        }
        return out.toString();
    }
}
