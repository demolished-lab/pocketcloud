package org.pocketcloud.supervisor;

import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;

public final class PhoneIdentity {
    private static final String ALIAS = "pocketcloud_phone_identity_p256_v1";
    public final byte[] publicKeyDer;
    public final String phoneId;
    private final PrivateKey privateKey;

    private PhoneIdentity(byte[] der, PrivateKey key) {
        publicKeyDer = der;
        phoneId = PairingProtocol.hex(PairingProtocol.sha256(der));
        privateKey = key;
    }

    public static PhoneIdentity loadOrCreate() throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (!ks.containsAlias(ALIAS)) {
            KeyPairGenerator gen = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore");
            gen.initialize(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
                    .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
                    .setDigests(KeyProperties.DIGEST_SHA256)
                    .setUserAuthenticationRequired(false)
                    .build());
            gen.generateKeyPair();
            ks.load(null);
        }
        java.security.cert.Certificate certificate = ks.getCertificate(ALIAS);
        java.security.Key key = ks.getKey(ALIAS, null);
        if (certificate == null || !(key instanceof PrivateKey)) throw new IllegalStateException("Keystore identity is unavailable");
        byte[] der = certificate.getPublicKey().getEncoded();
        if (der == null || der.length == 0) throw new IllegalStateException("Keystore public key is unavailable");
        return new PhoneIdentity(der, (PrivateKey) key);
    }

    public String signBase64Url(byte[] transcript) throws Exception {
        Signature signer = Signature.getInstance("SHA256withECDSA");
        signer.initSign(privateKey);
        signer.update(transcript);
        return Base64.encodeToString(signer.sign(), Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP);
    }
}
