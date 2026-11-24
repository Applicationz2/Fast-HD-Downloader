package org.fastdl.mobile;

import java.net.URI;
import java.util.List;

interface MediaSource {
    enum Access { AUTHORIZED_CLEAR, RESTRICTED, UNKNOWN }
    final class Format {
        final URI uri;
        final String mimeType;
        final int height;
        Format(URI uri, String mimeType, int height) {
            if (uri == null || !"https".equalsIgnoreCase(uri.getScheme())
                    || uri.getHost() == null || uri.getUserInfo() != null)
                throw new IllegalArgumentException("HTTPS media required");
            if (height < 0) throw new IllegalArgumentException("Invalid height");
            this.uri = uri;
            this.mimeType = mimeType;
            this.height = height;
        }
    }
    final class Result {
        final Access access;
        final List<Format> formats;
        Result(Access access, List<Format> formats) {
            this.access = java.util.Objects.requireNonNull(access);
            this.formats = access == Access.AUTHORIZED_CLEAR
                    ? java.util.Collections.unmodifiableList(new java.util.ArrayList<>(formats))
                    : java.util.Collections.emptyList();
        }
    }
    // Implementations must resolve only permitted sources, never bypass DRM,
    // and return UNKNOWN when authorization or protection cannot be determined.
    Result resolve(URI source) throws java.io.IOException;
}
