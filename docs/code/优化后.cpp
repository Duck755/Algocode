// redis_sds.cpp — Redis SDS (Simple Dynamic String) 独立版（C/C++ 兼容）
// 来源: https://github.com/antirez/sds
// 许可: BSD-2-Clause
//
// 编译: g++ -O2 -std=c++17 redis_sds.cpp -o redis_sds
//   或: gcc -O2 redis_sds.cpp -o redis_sds
// 运行: ./redis_sds

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
#include <ctype.h>
#include <assert.h>
#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif


// ==== 前置声明与常量 ====
// 原版定义在文件末尾，但被中间的函数使用，必须前置。

#define SDS_MAX_PREALLOC (1024*1024)

void *s_malloc(size_t size);
void *s_realloc(void *ptr, size_t size);
void s_free(void *ptr);


// ==== sds.h ====

typedef char *sds;

struct __attribute__ ((__packed__)) sdshdr5 {
    unsigned char flags;
    char buf[];
};
struct __attribute__ ((__packed__)) sdshdr8 {
    uint8_t len;
    uint8_t alloc;
    unsigned char flags;
    char buf[];
};
struct __attribute__ ((__packed__)) sdshdr16 {
    uint16_t len;
    uint16_t alloc;
    unsigned char flags;
    char buf[];
};
struct __attribute__ ((__packed__)) sdshdr32 {
    uint32_t len;
    uint32_t alloc;
    unsigned char flags;
    char buf[];
};
struct __attribute__ ((__packed__)) sdshdr64 {
    uint64_t len;
    uint64_t alloc;
    unsigned char flags;
    char buf[];
};

#define SDS_TYPE_5  0
#define SDS_TYPE_8  1
#define SDS_TYPE_16 2
#define SDS_TYPE_32 3
#define SDS_TYPE_64 4
#define SDS_TYPE_MASK 7
#define SDS_TYPE_BITS 3

// 原版用 (void*) 隐式转换，在 C++ 下非法。改为先转 char* 再做指针算术。
#define SDS_HDR_VAR(T,s) struct sdshdr##T *sh = \
    (struct sdshdr##T *)((char*)(s) - sizeof(struct sdshdr##T));
#define SDS_HDR(T,s) ((struct sdshdr##T *) \
    ((char*)(s) - sizeof(struct sdshdr##T)))
#define SDS_TYPE_5_LEN(f) ((f)>>SDS_TYPE_BITS)

static inline size_t sdslen(const sds s) {
    unsigned char flags = s[-1];
    switch(flags&SDS_TYPE_MASK) {
        case SDS_TYPE_5: {
            return SDS_TYPE_5_LEN(flags);
        }
        case SDS_TYPE_8: {
            SDS_HDR_VAR(8,s);
            return sh->len;
        }
        case SDS_TYPE_16: {
            SDS_HDR_VAR(16,s);
            return sh->len;
        }
        case SDS_TYPE_32: {
            SDS_HDR_VAR(32,s);
            return sh->len;
        }
        case SDS_TYPE_64: {
            SDS_HDR_VAR(64,s);
            return sh->len;
        }
    }
    return 0;
}

static inline size_t sdsavail(const sds s) {
    unsigned char flags = s[-1];
    switch(flags&SDS_TYPE_MASK) {
        case SDS_TYPE_5: {
            return 0;
        }
        case SDS_TYPE_8: {
            SDS_HDR_VAR(8,s);
            return sh->alloc - sh->len;
        }
        case SDS_TYPE_16: {
            SDS_HDR_VAR(16,s);
            return sh->alloc - sh->len;
        }
        case SDS_TYPE_32: {
            SDS_HDR_VAR(32,s);
            return sh->alloc - sh->len;
        }
        case SDS_TYPE_64: {
            SDS_HDR_VAR(64,s);
            return sh->alloc - sh->len;
        }
    }
    return 0;
}

static inline void sdssetlen(sds s, size_t newlen) {
    unsigned char flags = s[-1];
    switch(flags&SDS_TYPE_MASK) {
        case SDS_TYPE_5: {
            unsigned char *fp = ((unsigned char*)s)-1;
            *fp = SDS_TYPE_5 | (newlen << SDS_TYPE_BITS);
            break;
        }
        case SDS_TYPE_8: {
            SDS_HDR(8,s)->len = newlen;
            break;
        }
        case SDS_TYPE_16: {
            SDS_HDR(16,s)->len = newlen;
            break;
        }
        case SDS_TYPE_32: {
            SDS_HDR(32,s)->len = newlen;
            break;
        }
        case SDS_TYPE_64: {
            SDS_HDR(64,s)->len = newlen;
            break;
        }
    }
}

static inline void sdsinclen(sds s, size_t inc) {
    unsigned char flags = s[-1];
    switch(flags&SDS_TYPE_MASK) {
        case SDS_TYPE_5: {
            unsigned char *fp = ((unsigned char*)s)-1;
            unsigned char newlen = SDS_TYPE_5_LEN(flags)+inc;
            *fp = SDS_TYPE_5 | (newlen << SDS_TYPE_BITS);
            break;
        }
        case SDS_TYPE_8: {
            SDS_HDR(8,s)->len += inc;
            break;
        }
        case SDS_TYPE_16: {
            SDS_HDR(16,s)->len += inc;
            break;
        }
        case SDS_TYPE_32: {
            SDS_HDR(32,s)->len += inc;
            break;
        }
        case SDS_TYPE_64: {
            SDS_HDR(64,s)->len += inc;
            break;
        }
    }
}

static inline size_t sdsalloc(const sds s) {
    unsigned char flags = s[-1];
    switch(flags&SDS_TYPE_MASK) {
        case SDS_TYPE_5:
            return SDS_TYPE_5_LEN(flags);
        case SDS_TYPE_8:
            return SDS_HDR(8,s)->alloc;
        case SDS_TYPE_16:
            return SDS_HDR(16,s)->alloc;
        case SDS_TYPE_32:
            return SDS_HDR(32,s)->alloc;
        case SDS_TYPE_64:
            return SDS_HDR(64,s)->alloc;
    }
    return 0;
}

static inline void sdssetalloc(sds s, size_t newlen) {
    unsigned char flags = s[-1];
    switch(flags&SDS_TYPE_MASK) {
        case SDS_TYPE_5:
            break;
        case SDS_TYPE_8:
            SDS_HDR(8,s)->alloc = (uint8_t)newlen;
            break;
        case SDS_TYPE_16:
            SDS_HDR(16,s)->alloc = (uint16_t)newlen;
            break;
        case SDS_TYPE_32:
            SDS_HDR(32,s)->alloc = (uint32_t)newlen;
            break;
        case SDS_TYPE_64:
            SDS_HDR(64,s)->alloc = (uint64_t)newlen;
            break;
    }
}

sds sdsnewlen(const void *init, size_t initlen);
sds sdsnew(const char *init);
sds sdsempty(void);
sds sdsdup(const sds s);
void sdsfree(sds s);
sds sdsgrowzero(sds s, size_t len);
sds sdscatlen(sds s, const void *t, size_t len);
sds sdscat(sds s, const char *t);
sds sdscatsds(sds s, const sds t);
sds sdscpylen(sds s, const char *t, size_t len);
sds sdscpy(sds s, const char *t);

sds sdscatvprintf(sds s, const char *fmt, va_list ap);
sds sdscatprintf(sds s, const char *fmt, ...);
sds sdscatfmt(sds s, char const *fmt, ...);
sds sdstrim(sds s, const char *cset);
void sdsrange(sds s, ssize_t start, ssize_t end);
void sdsupdatelen(sds s);
void sdsclear(sds s);
int sdscmp(const sds s1, const sds s2);
sds *sdssplitlen(const char *s, ssize_t len, const char *sep, int seplen, int *count);
void sdsfreesplitres(sds *tokens, int count);
void sdstolower(sds s);
void sdstoupper(sds s);
sds sdsfromlonglong(long long value);
sds sdscatrepr(sds s, const char *p, size_t len);
sds *sdssplitargs(const char *line, int *argc);
sds sdsmapchars(sds s, const char *from, const char *to, size_t setlen);
sds sdsjoin(char **argv, int argc, char *sep);

sds sdsMakeRoomFor(sds s, size_t addlen);
void sdsIncrLen(sds s, ssize_t incr);
sds sdsRemoveFreeSpace(sds s);
size_t sdsAllocSize(sds s);
void *sdsAllocPtr(sds s);

void *sds_malloc(size_t size);
void *sds_realloc(void *ptr, size_t size);
void sds_free(void *ptr);


// ==== sds.c ====

static inline int sdsHdrSize(char type) {
    switch(type&SDS_TYPE_MASK) {
        case SDS_TYPE_5:
            return sizeof(struct sdshdr5);
        case SDS_TYPE_8:
            return sizeof(struct sdshdr8);
        case SDS_TYPE_16:
            return sizeof(struct sdshdr16);
        case SDS_TYPE_32:
            return sizeof(struct sdshdr32);
        case SDS_TYPE_64:
            return sizeof(struct sdshdr64);
    }
    return 0;
}

static inline char sdsReqType(size_t string_size) {
    if (string_size < 1<<5)
        return SDS_TYPE_5;
    if (string_size < 1<<8)
        return SDS_TYPE_8;
    if (string_size < 1<<16)
        return SDS_TYPE_16;
#if (LONG_MAX == LLONG_MAX)
    if (string_size < 1ll<<32)
        return SDS_TYPE_32;
    return SDS_TYPE_64;
#else
    return SDS_TYPE_32;
#endif
}

sds sdsnewlen(const void *init, size_t initlen) {
    void *sh;
    sds s;
    char type = sdsReqType(initlen);
    if (type == SDS_TYPE_5 && initlen == 0) type = SDS_TYPE_8;
    int hdrlen = sdsHdrSize(type);
    unsigned char *fp;

    sh = s_malloc(hdrlen+initlen+1);
    if (sh == NULL) return NULL;
    if (!init)
        memset(sh, 0, hdrlen+initlen+1);
    s = (char*)sh+hdrlen;
    fp = ((unsigned char*)s)-1;
    switch(type) {
        case SDS_TYPE_5: {
            *fp = type | (initlen << SDS_TYPE_BITS);
            break;
        }
        case SDS_TYPE_8: {
            SDS_HDR_VAR(8,s);
            sh->len = (uint8_t)initlen;
            sh->alloc = (uint8_t)initlen;
            *fp = type;
            break;
        }
        case SDS_TYPE_16: {
            SDS_HDR_VAR(16,s);
            sh->len = (uint16_t)initlen;
            sh->alloc = (uint16_t)initlen;
            *fp = type;
            break;
        }
        case SDS_TYPE_32: {
            SDS_HDR_VAR(32,s);
            sh->len = (uint32_t)initlen;
            sh->alloc = (uint32_t)initlen;
            *fp = type;
            break;
        }
        case SDS_TYPE_64: {
            SDS_HDR_VAR(64,s);
            sh->len = (uint64_t)initlen;
            sh->alloc = (uint64_t)initlen;
            *fp = type;
            break;
        }
    }
    if (initlen && init)
        memcpy(s, init, initlen);
    s[initlen] = '\0';
    return s;
}

sds sdsempty(void) {
    return sdsnewlen("",0);
}

sds sdsnew(const char *init) {
    size_t initlen = (init == NULL) ? 0 : strlen(init);
    return sdsnewlen(init, initlen);
}

sds sdsdup(const sds s) {
    return sdsnewlen(s, sdslen(s));
}

void sdsfree(sds s) {
    if (s == NULL) return;
    s_free((char*)s-sdsHdrSize(s[-1]));
}

void sdsupdatelen(sds s) {
    size_t reallen = strlen(s);
    sdssetlen(s, reallen);
}

void sdsclear(sds s) {
    sdssetlen(s, 0);
    s[0] = '\0';
}

sds sdsMakeRoomFor(sds s, size_t addlen) {
    void *sh, *newsh;
    size_t avail = sdsavail(s);
    size_t len, newlen;
    char type, oldtype = s[-1] & SDS_TYPE_MASK;
    int hdrlen;

    if (avail >= addlen) return s;

    len = sdslen(s);
    sh = (char*)s-sdsHdrSize(oldtype);
    newlen = (len+addlen);
    if (newlen < SDS_MAX_PREALLOC)
        newlen *= 2;
    else
        newlen += SDS_MAX_PREALLOC;

    type = sdsReqType(newlen);

    if (type == SDS_TYPE_5) type = SDS_TYPE_8;

    hdrlen = sdsHdrSize(type);
    if (oldtype==type) {
        newsh = s_realloc(sh, hdrlen+newlen+1);
        if (newsh == NULL) return NULL;
        s = (char*)newsh+hdrlen;
    } else {
        newsh = s_malloc(hdrlen+newlen+1);
        if (newsh == NULL) return NULL;
        memcpy((char*)newsh+hdrlen, s, len+1);
        s_free(sh);
        s = (char*)newsh+hdrlen;
        s[-1] = type;
        sdssetlen(s, len);
    }
    sdssetalloc(s, newlen);
    return s;
}

sds sdsRemoveFreeSpace(sds s) {
    void *sh, *newsh;
    char type, oldtype = s[-1] & SDS_TYPE_MASK;
    int hdrlen, oldhdrlen = sdsHdrSize(oldtype);
    size_t len = sdslen(s);
    sh = (char*)s-oldhdrlen;

    type = sdsReqType(len);
    hdrlen = sdsHdrSize(type);
    if (oldtype==type || type > SDS_TYPE_8) {
        newsh = s_realloc(sh, oldhdrlen+len+1);
        if (newsh == NULL) return NULL;
        s = (char*)newsh+oldhdrlen;
    } else {
        newsh = s_malloc(hdrlen+len+1);
        if (newsh == NULL) return NULL;
        memcpy((char*)newsh+hdrlen, s, len+1);
        s_free(sh);
        s = (char*)newsh+hdrlen;
        s[-1] = type;
        sdssetlen(s, len);
    }
    sdssetalloc(s, len);
    return s;
}

size_t sdsAllocSize(sds s) {
    size_t alloc = sdsalloc(s);
    return sdsHdrSize(s[-1])+alloc+1;
}

void *sdsAllocPtr(sds s) {
    return (void*) (s-sdsHdrSize(s[-1]));
}

void sdsIncrLen(sds s, ssize_t incr) {
    unsigned char flags = s[-1];
    size_t len;
    switch(flags&SDS_TYPE_MASK) {
        case SDS_TYPE_5: {
            unsigned char *fp = ((unsigned char*)s)-1;
            unsigned char oldlen = SDS_TYPE_5_LEN(flags);
            assert((incr > 0 && oldlen+incr < 32) || (incr < 0 && oldlen >= (unsigned int)(-incr)));
            *fp = SDS_TYPE_5 | ((oldlen+incr) << SDS_TYPE_BITS);
            len = oldlen+incr;
            break;
        }
        case SDS_TYPE_8: {
            SDS_HDR_VAR(8,s);
            assert((incr >= 0 && sh->alloc-sh->len >= incr) || (incr < 0 && sh->len >= (unsigned int)(-incr)));
            len = (sh->len += incr);
            break;
        }
        case SDS_TYPE_16: {
            SDS_HDR_VAR(16,s);
            assert((incr >= 0 && sh->alloc-sh->len >= incr) || (incr < 0 && sh->len >= (unsigned int)(-incr)));
            len = (sh->len += incr);
            break;
        }
        case SDS_TYPE_32: {
            SDS_HDR_VAR(32,s);
            assert((incr >= 0 && sh->alloc-sh->len >= (unsigned int)incr) || (incr < 0 && sh->len >= (unsigned int)(-incr)));
            len = (sh->len += incr);
            break;
        }
        case SDS_TYPE_64: {
            SDS_HDR_VAR(64,s);
            assert((incr >= 0 && sh->alloc-sh->len >= (uint64_t)incr) || (incr < 0 && sh->len >= (uint64_t)(-incr)));
            len = (sh->len += incr);
            break;
        }
        default: len = 0;
    }
    s[len] = '\0';
}

sds sdsgrowzero(sds s, size_t len) {
    size_t curlen = sdslen(s);

    if (len <= curlen) return s;
    s = sdsMakeRoomFor(s,len-curlen);
    if (s == NULL) return NULL;

    memset(s+curlen,0,(len-curlen+1));
    sdssetlen(s, len);
    return s;
}

sds sdscatlen(sds s, const void *t, size_t len) {
    size_t curlen = sdslen(s);

    s = sdsMakeRoomFor(s,len);
    if (s == NULL) return NULL;
    memcpy(s+curlen, t, len);
    sdssetlen(s, curlen+len);
    s[curlen+len] = '\0';
    return s;
}

sds sdscat(sds s, const char *t) {
    return sdscatlen(s, t, strlen(t));
}

sds sdscatsds(sds s, const sds t) {
    return sdscatlen(s, t, sdslen(t));
}

sds sdscpylen(sds s, const char *t, size_t len) {
    if (sdsalloc(s) < len) {
        s = sdsMakeRoomFor(s,len-sdslen(s));
        if (s == NULL) return NULL;
    }
    memcpy(s, t, len);
    s[len] = '\0';
    sdssetlen(s, len);
    return s;
}

sds sdscpy(sds s, const char *t) {
    return sdscpylen(s, t, strlen(t));
}

#define SDS_LLSTR_SIZE 21
int sdsll2str(char *s, long long value) {
    char *p, aux;
    unsigned long long v;
    size_t l;

    v = (value < 0) ? -value : value;
    p = s;
    do {
        *p++ = '0'+(v%10);
        v /= 10;
    } while(v);
    if (value < 0) *p++ = '-';

    l = p-s;
    *p = '\0';

    p--;
    while(s < p) {
        aux = *s;
        *s = *p;
        *p = aux;
        s++;
        p--;
    }
    return (int)l;
}

int sdsull2str(char *s, unsigned long long v) {
    char *p, aux;
    size_t l;

    p = s;
    do {
        *p++ = '0'+(v%10);
        v /= 10;
    } while(v);

    l = p-s;
    *p = '\0';

    p--;
    while(s < p) {
        aux = *s;
        *s = *p;
        *p = aux;
        s++;
        p--;
    }
    return (int)l;
}

sds sdsfromlonglong(long long value) {
    char buf[SDS_LLSTR_SIZE];
    int len = sdsll2str(buf,value);

    return sdsnewlen(buf,len);
}

/* Fast-format helpers: handle the restricted subset of formats that consist
 * only of literal bytes, "%%", "%d" (int) and "%s" (C string), without flags,
 * width, precision or length modifiers. For that subset the produced bytes are
 * identical to vsnprintf, but far cheaper. Anything else is rejected here so
 * that sdscatvprintf falls back to the exact libc vsnprintf path. */
static int sdssimplefmt(const char *fmt) {
    const char *p = fmt;
    while (*p) {
        if (*p == '%') {
            p++;
            if (*p == 'd' || *p == 's') { p++; continue; }
            if (*p == '%') { p++; continue; }
            return 0;
        }
        p++;
    }
    return 1;
}

/* Returns the exact number of bytes the simple formatter would produce, or
 * (size_t)-1 when a "%s" argument is NULL (caller must then use vsnprintf,
 * which prints "(null)"). Does not consume the caller's va_list. */
static size_t sdssimplelen(const char *fmt, va_list ap) {
    const char *p = fmt;
    size_t n = 0;
    va_list cpy;
    va_copy(cpy, ap);
    while (*p) {
        if (*p == '%') {
            p++;
            if (*p == 'd') {
                long long v = va_arg(cpy, int);
                unsigned long long u;
                if (v < 0) { n++; u = (unsigned long long)(-v); }
                else u = (unsigned long long)v;
                do { n++; u /= 10; } while (u);
                p++;
            } else if (*p == 's') {
                const char *sp = va_arg(cpy, const char *);
                if (sp == NULL) { va_end(cpy); return (size_t)-1; }
                n += strlen(sp);
                p++;
            } else {
                n++; p++;
            }
        } else {
            n++; p++;
        }
    }
    va_end(cpy);
    return n;
}

/* Writes exactly the bytes counted by sdssimplelen into dst. */
static void sdssimplewrite(char *dst, const char *fmt, va_list ap) {
    const char *p = fmt;
    while (*p) {
        if (*p == '%') {
            p++;
            if (*p == 'd') {
                char tmp[24];
                int l = sdsll2str(tmp, (long long)va_arg(ap, int));
                memcpy(dst, tmp, (size_t)l);
                dst += l;
                p++;
            } else if (*p == 's') {
                const char *sp = va_arg(ap, const char *);
                size_t l = strlen(sp);
                memcpy(dst, sp, l);
                dst += l;
                p++;
            } else {
                *dst++ = '%'; p++;
            }
        } else {
            *dst++ = *p++;
        }
    }
}

/* Single-pass fused validate+emit for the simple subset. Writes the produced
 * bytes into dst (capacity cap) and returns the exact byte count. Returns
 * (size_t)-1 when the format is outside the subset, when a "%s" argument is
 * NULL, or when the output would exceed cap; the caller then falls back. Uses
 * va_copy, so the caller's va_list is never consumed. */
static size_t sdssimpleemit(char *dst, size_t cap, const char *fmt, va_list ap) {
    char *out = dst;
    const char *p = fmt;
    va_list cpy;
    va_copy(cpy, ap);
    while (*p) {
        if (*p == '%') {
            p++;
            if (*p == 'd') {
                char tmp[SDS_LLSTR_SIZE];
                int l = sdsll2str(tmp, (long long)va_arg(cpy, int));
                if ((size_t)(out - dst) + (size_t)l > cap) { va_end(cpy); return (size_t)-1; }
                memcpy(out, tmp, (size_t)l);
                out += l;
                p++;
            } else if (*p == 's') {
                const char *sp = va_arg(cpy, const char *);
                if (sp == NULL) { va_end(cpy); return (size_t)-1; }
                size_t l = strlen(sp);
                if ((size_t)(out - dst) + l > cap) { va_end(cpy); return (size_t)-1; }
                memcpy(out, sp, l);
                out += l;
                p++;
            } else if (*p == '%') {
                if ((size_t)(out - dst) + 1 > cap) { va_end(cpy); return (size_t)-1; }
                *out++ = '%';
                p++;
            } else {
                va_end(cpy);
                return (size_t)-1;
            }
        } else {
            if ((size_t)(out - dst) + 1 > cap) { va_end(cpy); return (size_t)-1; }
            *out++ = *p++;
        }
    }
    va_end(cpy);
    return (size_t)(out - dst);
}

sds sdscatvprintf(sds s, const char *fmt, va_list ap) {
    va_list cpy;
    char staticbuf[1024], *buf = staticbuf, *t;
    size_t buflen;

    /* Fast path: fuse validation, counting and emission into a single pass
     * over fmt, converting each %d once. Appended via sdscatlen so growth is
     * identical to the previous in-place fast path. */
    {
        size_t slen = sdssimpleemit(staticbuf, sizeof(staticbuf), fmt, ap);
        if (slen != (size_t)-1)
            return sdscatlen(s, staticbuf, slen);
    }

    /* Simple output that did not fit the stack buffer (or a NULL %s): fall back
     * to the two-pass in-place writer, preserving the exact growth rule. */
    if (sdssimplefmt(fmt)) {
        size_t slen = sdssimplelen(fmt, ap);
        if (slen != (size_t)-1) {
            size_t curlen = sdslen(s);
            s = sdsMakeRoomFor(s, slen);
            if (s == NULL) return NULL;
            va_copy(cpy, ap);
            sdssimplewrite(s+curlen, fmt, cpy);
            va_end(cpy);
            sdssetlen(s, curlen+slen);
            s[curlen+slen] = '\0';
            return s;
        }
    }

    buflen = strlen(fmt)*2;

    if (buflen > sizeof(staticbuf)) {
        buf = (char*)s_malloc(buflen);
        if (buf == NULL) return NULL;
    } else {
        buflen = sizeof(staticbuf);
    }

    while(1) {
        buf[buflen-2] = '\0';
        va_copy(cpy,ap);
        vsnprintf(buf, buflen, fmt, cpy);
        va_end(cpy);
        if (buf[buflen-2] != '\0') {
            if (buf != staticbuf) s_free(buf);
            buflen *= 2;
            buf = (char*)s_malloc(buflen);
            if (buf == NULL) return NULL;
            continue;
        }
        break;
    }

    t = sdscat(s, buf);
    if (buf != staticbuf) s_free(buf);
    return t;
}

sds sdscatprintf(sds s, const char *fmt, ...) {
    va_list ap;
    char *t;
    va_start(ap, fmt);
    t = sdscatvprintf(s,fmt,ap);
    va_end(ap);
    return t;
}

sds sdscatfmt(sds s, char const *fmt, ...) {
    size_t initlen = sdslen(s);
    const char *f = fmt;
    long i;
    va_list ap;

    va_start(ap,fmt);
    f = fmt;
    i = (long)initlen;
    while(*f) {
        char next, *str;
        size_t l;
        long long num;
        unsigned long long unum;

        if (sdsavail(s)==0) {
            s = sdsMakeRoomFor(s,1);
        }

        switch(*f) {
        case '%':
            next = *(f+1);
            f++;
            switch(next) {
            case 's':
            case 'S':
                str = va_arg(ap,char*);
                l = (next == 's') ? strlen(str) : sdslen(str);
                if (sdsavail(s) < l) {
                    s = sdsMakeRoomFor(s,l);
                }
                memcpy(s+i,str,l);
                sdsinclen(s,l);
                i += (long)l;
                break;
            case 'i':
            case 'I':
                if (next == 'i')
                    num = va_arg(ap,int);
                else
                    num = va_arg(ap,long long);
                {
                    char buf[SDS_LLSTR_SIZE];
                    l = sdsll2str(buf,num);
                    if (sdsavail(s) < l) {
                        s = sdsMakeRoomFor(s,l);
                    }
                    memcpy(s+i,buf,l);
                    sdsinclen(s,l);
                    i += (long)l;
                }
                break;
            case 'u':
            case 'U':
                if (next == 'u')
                    unum = va_arg(ap,unsigned int);
                else
                    unum = va_arg(ap,unsigned long long);
                {
                    char buf[SDS_LLSTR_SIZE];
                    l = sdsull2str(buf,unum);
                    if (sdsavail(s) < l) {
                        s = sdsMakeRoomFor(s,l);
                    }
                    memcpy(s+i,buf,l);
                    sdsinclen(s,l);
                    i += (long)l;
                }
                break;
            default:
                s[i++] = next;
                sdsinclen(s,1);
                break;
            }
            break;
        default:
            s[i++] = *f;
            sdsinclen(s,1);
            break;
        }
        f++;
    }
    va_end(ap);

    s[i] = '\0';
    return s;
}

sds sdstrim(sds s, const char *cset) {
    char *start, *end, *sp, *ep;
    size_t len;

    sp = start = s;
    ep = end = s+sdslen(s)-1;
    while(sp <= end && strchr(cset, *sp)) sp++;
    while(ep > sp && strchr(cset, *ep)) ep--;
    len = (sp > ep) ? 0 : ((ep-sp)+1);
    if (s != sp) memmove(s, sp, len);
    s[len] = '\0';
    sdssetlen(s,len);
    return s;
}

void sdsrange(sds s, ssize_t start, ssize_t end) {
    size_t newlen, len = sdslen(s);

    if (len == 0) return;
    if (start < 0) {
        start = len+start;
        if (start < 0) start = 0;
    }
    if (end < 0) {
        end = len+end;
        if (end < 0) end = 0;
    }
    newlen = (start > end) ? 0 : (end-start)+1;
    if (newlen != 0) {
        if (start >= (ssize_t)len) {
            newlen = 0;
        } else if (end >= (ssize_t)len) {
            end = len-1;
            newlen = (start > end) ? 0 : (end-start)+1;
        }
    } else {
        start = 0;
    }
    if (start && newlen) memmove(s, s+start, newlen);
    s[newlen] = 0;
    sdssetlen(s,newlen);
}

void sdstolower(sds s) {
    size_t len = sdslen(s), j;

    for (j = 0; j < len; j++) s[j] = tolower((unsigned char)s[j]);
}

void sdstoupper(sds s) {
    size_t len = sdslen(s), j;

    for (j = 0; j < len; j++) s[j] = toupper((unsigned char)s[j]);
}

int sdscmp(const sds s1, const sds s2) {
    size_t l1, l2, minlen;
    int cmp;

    l1 = sdslen(s1);
    l2 = sdslen(s2);
    minlen = (l1 < l2) ? l1 : l2;
    cmp = memcmp(s1,s2,minlen);
    if (cmp == 0) return (int)(l1-l2);
    return cmp;
}

sds *sdssplitlen(const char *s, ssize_t len, const char *sep, int seplen, int *count) {
    int elements = 0, slots = 5, start = 0, j;
    sds *tokens;

    if (seplen < 1 || len < 0) return NULL;

    tokens = (sds*)s_malloc(sizeof(sds)*slots);
    if (tokens == NULL) return NULL;

    if (len == 0) {
        *count = 0;
        return tokens;
    }
    for (j = 0; j < (len-(seplen-1)); j++) {
        if (slots < elements+2) {
            sds *newtokens;

            slots *= 2;
            newtokens = (sds*)s_realloc(tokens,sizeof(sds)*slots);
            if (newtokens == NULL) goto cleanup;
            tokens = newtokens;
        }
        if ((seplen == 1 && *(s+j) == sep[0]) || (memcmp(s+j,sep,seplen) == 0)) {
            tokens[elements] = sdsnewlen(s+start,j-start);
            if (tokens[elements] == NULL) goto cleanup;
            elements++;
            start = j+seplen;
            j = j+seplen-1;
        }
    }
    tokens[elements] = sdsnewlen(s+start,len-start);
    if (tokens[elements] == NULL) goto cleanup;
    elements++;
    *count = elements;
    return tokens;

cleanup:
    {
        int i;
        for (i = 0; i < elements; i++) sdsfree(tokens[i]);
        s_free(tokens);
        *count = 0;
        return NULL;
    }
}

void sdsfreesplitres(sds *tokens, int count) {
    if (!tokens) return;
    while(count--)
        sdsfree(tokens[count]);
    s_free(tokens);
}

sds sdscatrepr(sds s, const char *p, size_t len) {
    s = sdscatlen(s,"\"",1);
    while(len--) {
        switch(*p) {
        case '\\':
        case '"':
            s = sdscatprintf(s,"\\%c",*p);
            break;
        case '\n': s = sdscatlen(s,"\\n",2); break;
        case '\r': s = sdscatlen(s,"\\r",2); break;
        case '\t': s = sdscatlen(s,"\\t",2); break;
        case '\a': s = sdscatlen(s,"\\a",2); break;
        case '\b': s = sdscatlen(s,"\\b",2); break;
        default:
            if (isprint((unsigned char)*p))
                s = sdscatprintf(s,"%c",*p);
            else
                s = sdscatprintf(s,"\\x%02x",(unsigned char)*p);
            break;
        }
        p++;
    }
    return sdscatlen(s,"\"",1);
}

int is_hex_digit(char c) {
    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
           (c >= 'A' && c <= 'F');
}

int hex_digit_to_int(char c) {
    switch(c) {
    case '0': return 0;
    case '1': return 1;
    case '2': return 2;
    case '3': return 3;
    case '4': return 4;
    case '5': return 5;
    case '6': return 6;
    case '7': return 7;
    case '8': return 8;
    case '9': return 9;
    case 'a': case 'A': return 10;
    case 'b': case 'B': return 11;
    case 'c': case 'C': return 12;
    case 'd': case 'D': return 13;
    case 'e': case 'E': return 14;
    case 'f': case 'F': return 15;
    default: return 0;
    }
}

sds *sdssplitargs(const char *line, int *argc) {
    const char *p = line;
    char *current = NULL;
    char **vector = NULL;

    *argc = 0;
    while(1) {
        while(*p && isspace((unsigned char)*p)) p++;
        if (*p) {
            int inq=0;
            int insq=0;
            int done=0;

            if (current == NULL) current = sdsempty();
            while(!done) {
                if (inq) {
                    if (*p == '\\' && *(p+1) == 'x' &&
                                             is_hex_digit(*(p+2)) &&
                                             is_hex_digit(*(p+3)))
                    {
                        unsigned char byte;

                        byte = (hex_digit_to_int(*(p+2))*16)+
                                hex_digit_to_int(*(p+3));
                        current = sdscatlen(current,(char*)&byte,1);
                        p += 3;
                    } else if (*p == '\\' && *(p+1)) {
                        char c;

                        p++;
                        switch(*p) {
                        case 'n': c = '\n'; break;
                        case 'r': c = '\r'; break;
                        case 't': c = '\t'; break;
                        case 'b': c = '\b'; break;
                        case 'a': c = '\a'; break;
                        default: c = *p; break;
                        }
                        current = sdscatlen(current,&c,1);
                    } else if (*p == '"') {
                        if (*(p+1) && !isspace((unsigned char)*(p+1))) goto err;
                        done=1;
                    } else if (!*p) {
                        goto err;
                    } else {
                        current = sdscatlen(current,p,1);
                    }
                } else if (insq) {
                    if (*p == '\\' && *(p+1) == '\'') {
                        p++;
                        current = sdscatlen(current,"'",1);
                    } else if (*p == '\'') {
                        if (*(p+1) && !isspace((unsigned char)*(p+1))) goto err;
                        done=1;
                    } else if (!*p) {
                        goto err;
                    } else {
                        current = sdscatlen(current,p,1);
                    }
                } else {
                    switch(*p) {
                    case ' ':
                    case '\n':
                    case '\r':
                    case '\t':
                    case '\0':
                        done=1;
                        break;
                    case '"':
                        inq=1;
                        break;
                    case '\'':
                        insq=1;
                        break;
                    default:
                        current = sdscatlen(current,p,1);
                        break;
                    }
                }
                if (*p) p++;
            }
            vector = (char**)s_realloc(vector,((*argc)+1)*sizeof(char*));
            vector[*argc] = current;
            (*argc)++;
            current = NULL;
        } else {
            if (vector == NULL) vector = (char**)s_malloc(sizeof(void*));
            return (sds*)vector;
        }
    }

err:
    while((*argc)--)
        sdsfree(vector[*argc]);
    s_free(vector);
    if (current) sdsfree(current);
    *argc = 0;
    return NULL;
}

sds sdsmapchars(sds s, const char *from, const char *to, size_t setlen) {
    size_t j, i, l = sdslen(s);

    for (j = 0; j < l; j++) {
        for (i = 0; i < setlen; i++) {
            if (s[j] == from[i]) {
                s[j] = to[i];
                break;
            }
        }
    }
    return s;
}

sds sdsjoin(char **argv, int argc, char *sep) {
    sds join = sdsempty();
    int j;

    for (j = 0; j < argc; j++) {
        join = sdscat(join, argv[j]);
        if (j != argc-1) join = sdscat(join,sep);
    }
    return join;
}

sds sdsjoinsds(sds *argv, int argc, const char *sep, size_t seplen) {
    sds join = sdsempty();
    int j;

    for (j = 0; j < argc; j++) {
        join = sdscatsds(join, argv[j]);
        if (j != argc-1) join = sdscatlen(join,sep,seplen);
    }
    return join;
}

void *s_malloc(size_t size) { return malloc(size); }
void *s_realloc(void *ptr, size_t size) { return realloc(ptr, size); }
void s_free(void *ptr) { free(ptr); }

void *sds_malloc(size_t size) { return s_malloc(size); }
void *sds_realloc(void *ptr, size_t size) { return s_realloc(ptr,size); }
void sds_free(void *ptr) { s_free(ptr); }


#ifdef __cplusplus
}  // extern "C"
#endif


// ==== Test Driver ====

int main() {
    printf("=== Redis SDS Benchmark ===\n");

    sds s = sdsempty();
    for (int i = 0; i < 100000; i++) {
        s = sdscatprintf(s, "line %d: hello world\n", i);
    }
    printf("After append: len=%zu, avail=%zu, alloc=%zu\n",
           sdslen(s), sdsavail(s), sdsalloc(s));

    sds dup = sdsdup(s);
    printf("Compare original vs dup: %d\n", sdscmp(s, dup));
    sdsfree(dup);

    sds trimmed = sdsnew("   hello world   ");
    sdstrim(trimmed, " ");
    printf("After trim: '%s' (len=%zu)\n", trimmed, sdslen(trimmed));
    sdsrange(trimmed, 0, 4);
    printf("After range(0,4): '%s' (len=%zu)\n", trimmed, sdslen(trimmed));
    sdsfree(trimmed);

    sds line = sdsnew("foo,bar,baz,qux");
    int count;
    sds *tokens = sdssplitlen(line, sdslen(line), ",", 1, &count);
    printf("Split into %d tokens: ", count);
    for (int i = 0; i < count; i++) {
        printf("'%s' ", tokens[i]);
    }
    printf("\n");
    sdsfreesplitres(tokens, count);
    sdsfree(line);

    sds num = sdsfromlonglong(123456789012345LL);
    printf("Number: %s\n", num);
    sdsfree(num);

    sdsfree(s);

    printf("=== Done ===\n");
    return 0;
}