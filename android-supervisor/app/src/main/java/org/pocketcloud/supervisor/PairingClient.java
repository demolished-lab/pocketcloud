package org.pocketcloud.supervisor;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;
import org.json.JSONObject;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.X509TrustManager;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

public final class PairingClient {
    private static final int MAX_BYTES = 8192;
    private static final int B64_FLAGS = Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP;
    private PairingClient() {}

    public static void pair(Context context, PairInvite invite, String phoneName) throws Exception {
        validatePhoneName(phoneName);
        if (invite.expiresAt < System.currentTimeMillis() / 1000L) throw new IllegalArgumentException("Invitation expired before approval");
        PhoneIdentity identity = PhoneIdentity.loadOrCreate();
        String phoneKeySha = PairingProtocol.hex(PairingProtocol.sha256(identity.publicKeyDer));
        String publicDer = Base64.encodeToString(identity.publicKeyDer, B64_FLAGS);
        byte[] transcript = PairingProtocol.transcript(invite.pairingId, invite.laptopId, identity.phoneId, phoneName, phoneKeySha, invite.nonce, invite.expiresAt);
        String signature = identity.signBase64Url(transcript);
        JSONObject body = new JSONObject();
        body.put("pairing_id", invite.pairingId);
        body.put("token", invite.token);
        body.put("phone_id", identity.phoneId);
        body.put("phone_name", phoneName);
        body.put("public_key_der", publicDer);
        body.put("signature", signature);
        byte[] request = body.toString().getBytes(StandardCharsets.UTF_8);
        if (request.length > MAX_BYTES) throw new IllegalArgumentException("Pairing request exceeds protocol size limit");

        URI uri = new URI("https", null, invite.host, invite.port, "/v1/pair", null, null);
        URL url = uri.toURL();
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        try {
            connection.setInstanceFollowRedirects(false);
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(5000);
            // The host waits for the laptop operator's explicit YES/denial before replying.
            connection.setReadTimeout(240_000);
            connection.setUseCaches(false);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json");
            connection.setRequestProperty("Accept", "application/json");
            connection.setFixedLengthStreamingMode(request.length);
            SSLContext tls = SSLContext.getInstance("TLS");
            tls.init(null, new javax.net.ssl.TrustManager[]{new PinTrustManager(invite.spkiSha256)}, null);
            connection.setSSLSocketFactory(tls.getSocketFactory());
            // Keep the platform's normal TLS hostname verifier: the certificate SAN must match the numeric URL host.
            connection.setHostnameVerifier(HttpsURLConnection.getDefaultHostnameVerifier());
            try (java.io.OutputStream out = connection.getOutputStream()) { out.write(request); }
            int status = connection.getResponseCode();
            InputStream responseStream = status >= 200 && status < 300 ? connection.getInputStream() : connection.getErrorStream();
            byte[] response = responseStream == null ? new byte[0] : readBounded(responseStream);
            if (status != 200) throw new IllegalStateException("Laptop rejected pairing or returned HTTP " + status);
            JSONObject result = new JSONObject(new String(response, StandardCharsets.UTF_8));
            requireKeys(result, new HashSet<>(Arrays.asList("paired", "laptop_id", "phone_id", "phone_key_sha256")));
            if (!result.getBoolean("paired") || !invite.laptopId.equals(result.getString("laptop_id")) || !identity.phoneId.equals(result.getString("phone_id")) || !phoneKeySha.equals(result.getString("phone_key_sha256")))
                throw new IllegalStateException("Laptop returned an invalid pairing response");
            SharedPreferences prefs = context.getSharedPreferences("paired_peers", Context.MODE_PRIVATE);
            if (!prefs.edit().putString("laptop_id", invite.laptopId).putString("phone_id", identity.phoneId)
                    .putString("laptop_spki_sha256", invite.spkiSha256).commit())
                throw new IllegalStateException("Could not save pairing identifiers");
        } finally { connection.disconnect(); }
    }

    private static byte[] readBounded(InputStream in) throws Exception {
        try (InputStream stream = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[1024]; int count, total = 0;
            while ((count = stream.read(buffer)) != -1) {
                total += count;
                if (total > MAX_BYTES) throw new IllegalStateException("Pairing response exceeds protocol size limit");
                out.write(buffer, 0, count);
            }
            return out.toByteArray();
        }
    }

    private static void requireKeys(JSONObject json, Set<String> expected) throws Exception {
        Set<String> keys = new HashSet<>();
        java.util.Iterator<String> it = json.keys();
        while (it.hasNext()) keys.add(it.next());
        if (!keys.equals(expected)) throw new IllegalStateException("Unexpected pairing response fields");
    }

    public static void validatePhoneName(String name) {
        PairInvite.requirePrintableDisplayName(name, "Phone name");
    }

    private static final class PinTrustManager implements X509TrustManager {
        private final byte[] expected;
        PinTrustManager(String pin) {
            expected = Base64.decode(pin, B64_FLAGS);
            if (expected.length != 32) throw new IllegalArgumentException("Invalid invitation pin");
        }
        @Override public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
            if (chain == null || chain.length == 0) throw new CertificateException("Missing server certificate");
            try {
                byte[] actual = MessageDigest.getInstance("SHA-256").digest(chain[0].getPublicKey().getEncoded());
                if (!MessageDigest.isEqual(expected, actual)) throw new CertificateException("Server certificate pin mismatch");
            } catch (CertificateException e) { throw e; }
            catch (Exception e) { throw new CertificateException("Could not verify server certificate", e); }
        }
        @Override public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException { throw new CertificateException("Client certificates are not accepted"); }
        @Override public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
    }
}
