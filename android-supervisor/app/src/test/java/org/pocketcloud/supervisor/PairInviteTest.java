package org.pocketcloud.supervisor;

import static org.junit.Assert.*;
import org.junit.Test;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

public class PairInviteTest {
    private static String b64(byte fill) { byte[] b = new byte[32]; java.util.Arrays.fill(b, fill); return Base64.getUrlEncoder().withoutPadding().encodeToString(b); }
    private static String invite(String host, String expiry, String token) {
        return "pocketcloud://pair?v=1&host=" + host + "&port=8765&laptop_id=11111111-1111-4111-8111-111111111111&laptop_name=Work%20Laptop&pairing_id=22222222-2222-4222-8222-222222222222&expires_at=" + expiry + "&nonce=" + b64((byte)1) + "&token=" + token + "&spki_sha256=" + b64((byte)2);
    }
    @Test public void parsesPrivateIpv4Invite() {
        PairInvite p = PairInvite.parse(invite("192.168.1.8", Long.toString(System.currentTimeMillis()/1000+120), b64((byte)3)));
        assertEquals("192.168.1.8", p.host); assertEquals(8765, p.port); assertEquals("Work Laptop", p.laptopName);
    }
    @Test public void parsesIpv6UlaInvite() {
        PairInvite p = PairInvite.parse(invite("fd12:3456::8", Long.toString(System.currentTimeMillis()/1000+120), b64((byte)3)));
        assertEquals("fd12:3456::8", p.host);
    }
    @Test public void rejectsPublicAndDnsHosts() {
        assertFalse(PairInvite.isPrivateNumericHost("8.8.8.8"));
        assertFalse(PairInvite.isPrivateNumericHost("laptop.local"));
        assertFalse(PairInvite.isPrivateNumericHost("127.0.0.1"));
        assertFalse(PairInvite.isPrivateNumericHost("224.0.0.1"));
        assertTrue(PairInvite.isPrivateNumericHost("fd12:3456::1"));
        assertFalse(PairInvite.isPrivateNumericHost("2001:4860:4860::8888"));
    }
    @Test public void rejectsTamperingDuplicateAndExtraFields() {
        String s = invite("10.1.2.3", Long.toString(System.currentTimeMillis()/1000+120), b64((byte)3));
        try { PairInvite.parse(s.replace("port=8765", "port=0")); fail(); } catch (IllegalArgumentException expected) {}
        try { PairInvite.parse(s + "&extra=x"); fail(); } catch (IllegalArgumentException expected) {}
        try { PairInvite.parse(s + "&port=8765"); fail(); } catch (IllegalArgumentException expected) {}
        try { PairInvite.parse(s.replace("token=" + b64((byte)3), "token=abc=")); fail(); } catch (IllegalArgumentException expected) {}
    }
    @Test public void rejectsExpiredInvite() {
        String s = invite("10.1.2.3", Long.toString(System.currentTimeMillis()/1000-1), b64((byte)3));
        try { PairInvite.parse(s); fail(); } catch (IllegalArgumentException expected) {}
    }
    @Test public void base64UrlMustBeCanonicalUnpaddedEncoding() {
        byte[] expected = new byte[]{1};
        assertArrayEquals(expected, Base64Url.decode("AQ"));
        assertEquals("AQ", Base64Url.encode(expected));
        for (String invalid : new String[]{"AQ==", "AR", "A", "!"}) {
            try { Base64Url.decode(invalid); fail("accepted " + invalid); } catch (IllegalArgumentException expectedError) {}
        }
    }
    @Test public void displayNamesRejectInvisibleFormatsAndNonAsciiSeparators() {
        String valid = invite("10.1.2.3", Long.toString(System.currentTimeMillis()/1000+120), b64((byte)3));
        for (String encoded : new String[]{"Phone%E2%80%AEName", "Phone%E2%80%87Name"}) {
            try { PairInvite.parse(valid.replace("Work%20Laptop", encoded)); fail("accepted QR name " + encoded); }
            catch (IllegalArgumentException expected) {}
        }
        for (String invalid : new String[]{"Phone\u202eName", "Phone\u2007Name"}) {
            try { PairingClient.validatePhoneName(invalid); fail("accepted phone name"); }
            catch (IllegalArgumentException expected) {}
        }
        PairingClient.validatePhoneName("PocketCloud 📱");
    }
    @Test public void transcriptHasExactFieldsAndFinalNewline() {
        String expected = "pocketcloud-pair-v1\nP\nL\nI\nPhone\nabc\nnonce\n123\n";
        assertArrayEquals(expected.getBytes(StandardCharsets.UTF_8), PairingProtocol.transcript("P","L","I","Phone","abc","nonce",123));
    }
}
