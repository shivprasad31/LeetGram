(() => {
  const config = window.codeArenaRegisterConfig;
  const form = document.getElementById("otp-register-form");
  if (!config || !form) {
    return;
  }

  const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]")?.value;
  const usernameInput = document.getElementById("id_username");
  const emailInput = document.getElementById("id_email");
  const password1Input = document.getElementById("id_password1");
  const password2Input = document.getElementById("id_password2");
  const otpInput = document.getElementById("id_otp");
  const sendOtpButton = document.getElementById("send-otp-button");
  const verifyOtpButton = document.getElementById("verify-otp-button");
  const editDetailsButton = document.getElementById("edit-details-button");
  const otpStage = document.getElementById("otp-stage");
  const feedback = document.getElementById("register-feedback");
  const usernameFeedback = document.getElementById("username-feedback");
  const emailFeedback = document.getElementById("email-feedback");
  const password1Feedback = document.getElementById("password1-feedback");
  const passwordMatchFeedback = document.getElementById("password-match-feedback");
  const otpFeedback = document.getElementById("otp-feedback");
  const timerLabel = document.getElementById("otp-timer-label");

  let usernameCheckTimer = null;
  let resendInterval = null;
  let resendRemaining = 0;
  let otpSent = false;

  const credentialInputs = [usernameInput, emailInput, password1Input, password2Input];

  const showBanner = (message, level) => {
    feedback.className = `alert alert-${level} rounded-4 mb-4`;
    feedback.textContent = message;
    feedback.classList.remove("d-none");
  };

  const hideBanner = () => {
    feedback.classList.add("d-none");
    feedback.textContent = "";
  };

  const setFieldMessage = (element, message, tone = "muted") => {
    if (!element) {
      return;
    }
    element.textContent = message;
    element.className = `inline-feedback mt-2 feedback-${tone}`;
  };

  const setButtonLoading = (button, loadingText, isLoading) => {
    if (!button) {
      return;
    }
    if (!button.dataset.defaultText) {
      button.dataset.defaultText = button.innerHTML;
    }
    button.disabled = isLoading;
    button.innerHTML = isLoading
      ? `<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>${loadingText}`
      : button.dataset.defaultText;
  };

  const setCredentialsLocked = (locked) => {
    credentialInputs.forEach((input) => {
      input.readOnly = locked;
    });
    editDetailsButton.classList.toggle("d-none", !locked);
  };

  const stopTimer = () => {
    if (resendInterval) {
      window.clearInterval(resendInterval);
      resendInterval = null;
    }
  };

  const updateSendButton = () => {
    if (resendRemaining > 0) {
      sendOtpButton.disabled = true;
      sendOtpButton.textContent = `Resend OTP in ${resendRemaining}s`;
      timerLabel.textContent = `You can request a new code in ${resendRemaining}s`;
      return;
    }
    sendOtpButton.disabled = false;
    sendOtpButton.textContent = otpSent ? "Resend OTP" : "Send OTP";
    timerLabel.textContent = otpSent ? "You can resend the code now." : "";
  };

  const startTimer = (seconds) => {
    resendRemaining = Number(seconds) || 0;
    stopTimer();
    updateSendButton();
    if (resendRemaining <= 0) {
      return;
    }
    resendInterval = window.setInterval(() => {
      resendRemaining -= 1;
      updateSendButton();
      if (resendRemaining <= 0) {
        stopTimer();
      }
    }, 1000);
  };

  const validatePasswordMatch = () => {
    const password1 = password1Input.value;
    const password2 = password2Input.value;
    if (!password1 && !password2) {
      setFieldMessage(passwordMatchFeedback, "Re-enter the same password to continue.");
      return false;
    }
    if (password2 && password1 !== password2) {
      setFieldMessage(passwordMatchFeedback, "Passwords do not match.", "error");
      return false;
    }
    if (password2) {
      setFieldMessage(passwordMatchFeedback, "Passwords match.", "success");
    } else {
      setFieldMessage(passwordMatchFeedback, "Re-enter the same password to continue.");
    }
    return true;
  };

  const resetOtpState = (message = "", { preserveCooldown = true } = {}) => {
    otpSent = false;
    otpStage.classList.add("d-none");
    otpInput.value = "";
    setCredentialsLocked(false);
    if (!preserveCooldown) {
      stopTimer();
      resendRemaining = 0;
    }
    updateSendButton();
    if (message) {
      showBanner(message, "info");
    }
    setFieldMessage(otpFeedback, `The OTP expires in ${config.otpExpiryMinutes} minute${config.otpExpiryMinutes === 1 ? "" : "s"}.`);
  };

  const checkUsernameAvailability = async () => {
    const username = usernameInput.value.trim();
    if (!username) {
      setFieldMessage(usernameFeedback, "Pick a unique public username for your profile.");
      return;
    }
    if (username.length < 3) {
      setFieldMessage(usernameFeedback, "Use at least 3 characters.", "error");
      return;
    }

    setFieldMessage(usernameFeedback, "Checking availability...");
    try {
      const response = await fetch(`${config.checkUsernameUrl}?username=${encodeURIComponent(username)}`);
      const payload = await response.json();
      if (!response.ok || payload.available === false) {
        setFieldMessage(usernameFeedback, payload.message || "This username is unavailable.", "error");
        return;
      }
      setFieldMessage(usernameFeedback, payload.message || "This username is available.", "success");
    } catch (error) {
      setFieldMessage(usernameFeedback, "Could not check username right now.", "error");
    }
  };

  const sendOtp = async () => {
    hideBanner();
    if (!validatePasswordMatch()) {
      showBanner("Please fix the password confirmation before requesting an OTP.", "danger");
      return;
    }

    setButtonLoading(sendOtpButton, "Sending OTP...", true);
    const payload = new URLSearchParams({
      username: usernameInput.value.trim(),
      email: emailInput.value.trim(),
      password1: password1Input.value,
      password2: password2Input.value,
    });

    try {
      const response = await fetch(config.sendOtpUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
          "X-CSRFToken": csrfToken,
        },
        body: payload.toString(),
      });
      const data = await response.json();
      if (!response.ok) {
        showBanner(data.message || "We could not send the OTP.", response.status === 429 ? "warning" : "danger");
        const errors = data.errors || {};
        if (errors.username?.length) {
          setFieldMessage(usernameFeedback, errors.username[0], "error");
        }
        if (errors.email?.length) {
          setFieldMessage(emailFeedback, errors.email[0], "error");
        }
        if (errors.password1?.length) {
          setFieldMessage(password1Feedback, errors.password1[0], "error");
        }
        if (errors.password2?.length) {
          setFieldMessage(passwordMatchFeedback, errors.password2[0], "error");
        }
        if (data.retry_after) {
          resendRemaining = Number(data.retry_after);
        }
        updateSendButton();
        return;
      }

      otpSent = true;
      otpStage.classList.remove("d-none");
      setCredentialsLocked(true);
      showBanner(data.message, "success");
      setFieldMessage(emailFeedback, "OTP sent successfully. Use the code from your inbox.", "success");
      setFieldMessage(otpFeedback, "Enter the 6-digit OTP from your email to create the account.", "success");
      startTimer(data.retry_after || 60);
      otpInput.focus();
    } catch (error) {
      showBanner("Unexpected network error while sending OTP.", "danger");
    } finally {
      setButtonLoading(sendOtpButton, "Sending OTP...", false);
      updateSendButton();
    }
  };

  const verifyOtp = async () => {
    hideBanner();
    const otp = otpInput.value.trim();
    if (!otp || otp.length !== 6) {
      setFieldMessage(otpFeedback, "Enter the 6-digit OTP from your email.", "error");
      showBanner("Enter the OTP to finish registration.", "danger");
      return;
    }

    setButtonLoading(verifyOtpButton, "Verifying...", true);
    try {
      const response = await fetch(config.verifyOtpUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
          "X-CSRFToken": csrfToken,
        },
        body: new URLSearchParams({
          email: emailInput.value.trim(),
          otp,
        }).toString(),
      });
      const data = await response.json();
      if (!response.ok) {
        setFieldMessage(otpFeedback, data.message || "OTP verification failed.", "error");
        if (response.status === 429) {
          resetOtpState("OTP limit reached. Request a fresh code to continue.");
          return;
        }
        showBanner(data.message || "OTP verification failed.", "danger");
        return;
      }

      setFieldMessage(otpFeedback, "OTP verified successfully. Redirecting...", "success");
      showBanner("Account created successfully. Redirecting to profile setup...", "success");
      window.location.assign(data.redirect_url || config.loginUrl);
    } catch (error) {
      setFieldMessage(otpFeedback, "Unexpected network error while verifying OTP.", "error");
      showBanner("Unexpected network error while verifying OTP.", "danger");
    } finally {
      setButtonLoading(verifyOtpButton, "Verifying...", false);
    }
  };

  password1Input.addEventListener("input", () => {
    const hasValue = password1Input.value.length > 0;
    setFieldMessage(
      password1Feedback,
      hasValue ? "Keep it strong and avoid using personal details." : "Use at least 8 characters and avoid common passwords."
    );
    validatePasswordMatch();
  });

  password2Input.addEventListener("input", validatePasswordMatch);
  emailInput.addEventListener("input", () => {
    setFieldMessage(emailFeedback, "We will send a 6-digit OTP to this email address.");
  });

  usernameInput.addEventListener("input", () => {
    if (usernameCheckTimer) {
      window.clearTimeout(usernameCheckTimer);
    }
    usernameCheckTimer = window.setTimeout(checkUsernameAvailability, 350);
  });

  [usernameInput, emailInput, password1Input, password2Input].forEach((input) => {
    input.addEventListener("input", () => {
      if (otpSent && input.readOnly === false) {
        resetOtpState("Signup details changed. Please request a new OTP.");
      }
    });
  });

  form.querySelectorAll("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.querySelector(button.dataset.togglePassword);
      if (!target) {
        return;
      }
      const isPassword = target.type === "password";
      target.type = isPassword ? "text" : "password";
      button.innerHTML = isPassword ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
    });
  });

  sendOtpButton.addEventListener("click", sendOtp);
  verifyOtpButton.addEventListener("click", verifyOtp);
  editDetailsButton.addEventListener("click", () => resetOtpState("You can now edit your details. Request a new OTP when ready."));
  otpInput.addEventListener("input", () => {
    otpInput.value = otpInput.value.replace(/\D/g, "").slice(0, 6);
  });
  otpInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      verifyOtp();
    }
  });

  updateSendButton();
})();
