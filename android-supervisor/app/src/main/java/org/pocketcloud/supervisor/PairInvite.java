package org.pocketcloud.supervisor;

import java.net.Inet6Address;
import java.net.InetAddress;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** Validated, immutable representation of a PocketCloud v1 QR invitation. */
public final class PairInvite {
    private static final Set<String> FIELDS = Collections.unmodifiableSet(new HashSet<>(Arrays.asList("v", "host", "port", "laptop_id", "laptop_name", "pairing_id", "expires_at", "nonce", "token", "spki_sha256")));
    public final String host, laptopId, laptopName, pairingId, nonce, token, spkiSha256;
    public final int port;
    public final long expiresAt;

    private PairInvite(Map<String, String> q) {
        if (!"1".equals(q.get("v"))) throw new IllegalArgumentException("Unsupported invitation version");
        host = q.get("host");
        if (!isPrivateNumericHost(host)) throw new IllegalArgumentException("Invitation host must be a private numeric LAN address");
        try { if (!q.get("port").matches("[0-9]{1,5}")) throw new NumberFormatException(); port = Integer.parseInt(q.get("port")); }
        catch (RuntimeException e) { throw new IllegalArgumentException("Invalid port"); }
        if (port < 1 || port > 65535) throw new IllegalArgumentException("Invalid port");
        laptopId = canonicalUuid(q.get("laptop_id"));
        pairingId = canonicalUuid(q.get("pairing_id"));
        laptopName = printable(q.get("laptop_name"), 1, 64, "Laptop name");
        try {
            if (!q.get("expires_at").matches("[0-9]{1,12}")) throw new NumberFormatException();
            expiresAt = Long.parseLong(q.get("expires_at"));
        } catch (RuntimeException e) { throw new IllegalArgumentException("Invalid invitation expiry"); }
        long now = System.currentTimeMillis() / 1000L;
        if (expiresAt < now || expiresAt > now + 600) throw new IllegalArgumentException("Invitation is expired or has an unreasonable expiry");
        nonce = base64Url(q.get("nonce"), 32, "nonce");
        token = base64Url(q.get("token"), 32, "token");
        spkiSha256 = base64Url(q.get("spki_sha256"), 32, "SPKI fingerprint");
    }

    public static PairInvite parse(String text) {
        try {
            if (text == null || text.length() > 4096) throw new IllegalArgumentException("Invalid invitation");
            URI uri = new URI(text);
            if (!"pocketcloud".equals(uri.getScheme()) || !"pair".equals(uri.getHost()) || uri.getRawUserInfo() != null || uri.getPort() != -1 || (uri.getRawPath() != null && !uri.getRawPath().isEmpty()) || uri.getRawFragment() != null || uri.getRawQuery() == null)
                throw new IllegalArgumentException("Not a PocketCloud pairing invitation");
            Map<String, String> values = new HashMap<>();
            String[] parts = uri.getRawQuery().split("&", -1);
            if (parts.length != FIELDS.size()) throw new IllegalArgumentException("Invitation fields are incomplete or unexpected");
            for (String part : parts) {
                int eq = part.indexOf('=');
                if (eq <= 0) throw new IllegalArgumentException("Malformed invitation query");
                String key = URLDecoder.decode(part.substring(0, eq), "UTF-8");
                String value = URLDecoder.decode(part.substring(eq + 1), "UTF-8");
                if (!FIELDS.contains(key) || values.put(key, value) != null) throw new IllegalArgumentException("Unexpected or duplicate invitation field");
            }
            if (!values.keySet().equals(FIELDS)) throw new IllegalArgumentException("Invitation fields are incomplete");
            return new PairInvite(values);
        } catch (IllegalArgumentException e) { throw e; }
        catch (Exception e) { throw new IllegalArgumentException("Malformed pairing invitation"); }
    }

    private static String canonicalUuid(String s) {
        try {
            UUID u = UUID.fromString(s);
            if (!u.toString().equals(s)) throw new IllegalArgumentException("UUID must use canonical lowercase form");
            return s;
        } catch (RuntimeException e) { throw new IllegalArgumentException("Invalid UUID"); }
    }

    private static String printable(String s, int min, int max, String label) {
        if (s == null) throw new IllegalArgumentException("Invalid " + label);
        int count = s.codePointCount(0, s.length());
        if (count < min || count > max) throw new IllegalArgumentException("Invalid " + label);
        for (int i = 0; i < s.length();) {
            int cp = s.codePointAt(i);
            int type = Character.getType(cp);
            if (type == Character.CONTROL || type == Character.FORMAT || type == Character.SURROGATE
                    || type == Character.PRIVATE_USE || type == Character.UNASSIGNED
                    || type == Character.LINE_SEPARATOR || type == Character.PARAGRAPH_SEPARATOR
                    || (type == Character.SPACE_SEPARATOR && cp != 0x20))
                throw new IllegalArgumentException("Invalid " + label);
            i += Character.charCount(cp);
        }
        return s;
    }

    public static void requirePrintableDisplayName(String value, String label) {
        printable(value, 1, 64, label);
    }

    private static String base64Url(String s, int bytes, String label) {
        try {
            if (s == null || !s.matches("[A-Za-z0-9_-]+")) throw new IllegalArgumentException();
            byte[] decoded = Base64Url.decode(s);
            String canonical = Base64Url.encode(decoded);
            if (decoded.length != bytes || !canonical.equals(s)) throw new IllegalArgumentException();
            return s;
        } catch (RuntimeException e) { throw new IllegalArgumentException("Invalid " + label); }
    }

    /** Allows only RFC1918 IPv4 or IPv6 unique-local addresses; never resolves names. */
    public static boolean isPrivateNumericHost(String host) {
        if (host == null || host.isEmpty() || host.length() > 45 || host.indexOf('%') >= 0) return false;
        if (host.indexOf(':') < 0) {
            String[] octets = host.split("\\.", -1);
            if (octets.length != 4) return false;
            int[] b = new int[4];
            try {
                for (int i = 0; i < 4; i++) {
                    if (octets[i].isEmpty() || !octets[i].matches("[0-9]{1,3}") || (octets[i].length() > 1 && octets[i].charAt(0) == '0')) return false;
                    b[i] = Integer.parseInt(octets[i]);
                    if (b[i] > 255) return false;
                }
            } catch (NumberFormatException e) { return false; }
            return b[0] == 10 || (b[0] == 172 && b[1] >= 16 && b[1] <= 31) || (b[0] == 192 && b[1] == 168);
        }
        if (!host.matches("[0-9A-Fa-f:]+")) return false;
        try {
            InetAddress address = InetAddress.getByName(host); // ':' guarantees literal IPv6 parsing, no DNS lookup.
            if (!(address instanceof Inet6Address)) return false;
            byte[] b = address.getAddress();
            return (b[0] & 0xfe) == 0xfc; // fc00::/7 ULA excludes loopback, link-local, multicast and unspecified.
        } catch (Exception e) { return false; }
    }
}
