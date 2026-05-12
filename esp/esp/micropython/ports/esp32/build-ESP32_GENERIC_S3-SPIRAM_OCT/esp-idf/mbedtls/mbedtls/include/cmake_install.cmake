# Install script for directory: /workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/usr/local")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "TRUE")
endif()

# Set path to fallback-tool for dependency-resolution.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/opt/esp/tools/xtensa-esp-elf/esp-14.2.0_20241119/xtensa-esp-elf/bin/xtensa-esp32s3-elf-objdump")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/mbedtls" TYPE FILE PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ FILES
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/aes.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/aria.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/asn1.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/asn1write.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/base64.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/bignum.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/block_cipher.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/build_info.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/camellia.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ccm.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/chacha20.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/chachapoly.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/check_config.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/cipher.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/cmac.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/compat-2.x.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/config_adjust_legacy_crypto.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/config_adjust_legacy_from_psa.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/config_adjust_psa_from_legacy.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/config_adjust_psa_superset_legacy.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/config_adjust_ssl.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/config_adjust_x509.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/config_psa.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/constant_time.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ctr_drbg.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/debug.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/des.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/dhm.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ecdh.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ecdsa.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ecjpake.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ecp.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/entropy.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/error.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/gcm.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/hkdf.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/hmac_drbg.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/lms.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/mbedtls_config.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/md.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/md5.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/memory_buffer_alloc.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/net_sockets.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/nist_kw.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/oid.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/pem.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/pk.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/pkcs12.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/pkcs5.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/pkcs7.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/platform.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/platform_time.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/platform_util.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/poly1305.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/private_access.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/psa_util.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ripemd160.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/rsa.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/sha1.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/sha256.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/sha3.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/sha512.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ssl.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ssl_cache.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ssl_ciphersuites.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ssl_cookie.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/ssl_ticket.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/threading.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/timing.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/version.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/x509.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/x509_crl.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/x509_crt.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/mbedtls/x509_csr.h"
    )
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/psa" TYPE FILE PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ FILES
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/build_info.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_adjust_auto_enabled.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_adjust_config_dependencies.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_adjust_config_key_pair_types.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_adjust_config_synonyms.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_builtin_composites.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_builtin_key_derivation.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_builtin_primitives.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_compat.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_config.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_driver_common.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_driver_contexts_composites.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_driver_contexts_key_derivation.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_driver_contexts_primitives.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_extra.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_legacy.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_platform.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_se_driver.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_sizes.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_struct.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_types.h"
    "/workspace/esp/esp/esp-idf/components/mbedtls/mbedtls/include/psa/crypto_values.h"
    )
endif()

