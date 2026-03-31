import { ref, onMounted, watch } from "vue";
import gsap from "gsap";
const props = defineProps({
    modelValue: {
        type: Boolean,
        default: true
    }
});
const emit = defineEmits(["update:modelValue", "change"]);
const isDark = ref(props.modelValue);
const toggleRef = ref(null);
const bgRef = ref(null);
const textRef = ref(null);
const handleWrapperRef = ref(null);
const handleRef = ref(null);
const toggleTheme = () => {
    isDark.value = !isDark.value;
    emit("update:modelValue", isDark.value);
    emit("change", isDark.value);
    animate();
};
const animate = () => {
    if (isDark.value) {
        gsap.to(handleWrapperRef.value, { x: 0, duration: 0.5, ease: "power2.out" });
        gsap.to(handleRef.value, {
            boxShadow: "inset 9px -4px 0 0 #00506A",
            backgroundColor: "transparent",
            duration: 0.5,
            ease: "power2.out"
        });
        gsap.to(bgRef.value, {
            background: "linear-gradient(90deg, #0ce2f7, #d6f5ff)",
            duration: 0.5
        });
        gsap.to(textRef.value, {
            x: 35,
            color: "#00506A",
            duration: 0.5
        });
    }
    else {
        gsap.to(handleWrapperRef.value, { x: 60, duration: 0.5, ease: "power2.out" });
        gsap.to(handleRef.value, {
            boxShadow: "inset 0 0 0 0 transparent",
            backgroundColor: "#ffffff",
            duration: 0.5,
            ease: "power2.out"
        });
        gsap.to(bgRef.value, {
            background: "linear-gradient(90deg, #008eb5, #003B52)",
            duration: 0.5
        });
        gsap.to(textRef.value, {
            x: -12,
            color: "#ffffff",
            duration: 0.5
        });
    }
};
watch(() => props.modelValue, (val) => {
    if (isDark.value !== val) {
        isDark.value = val;
        animate();
    }
});
onMounted(() => {
    if (isDark.value) {
        gsap.set(handleWrapperRef.value, { x: 0 });
        gsap.set(handleRef.value, { boxShadow: "inset 9px -4px 0 0 #00506A", backgroundColor: "transparent" });
        gsap.set(bgRef.value, { background: "linear-gradient(90deg, #0ce2f7, #d6f5ff)" });
        gsap.set(textRef.value, { x: 35, color: "#00506A" });
    }
    else {
        gsap.set(handleWrapperRef.value, { x: 60 });
        gsap.set(handleRef.value, { boxShadow: "inset 0 0 0 0 transparent", backgroundColor: "#ffffff" });
        gsap.set(bgRef.value, { background: "linear-gradient(90deg, #008eb5, #003B52)" });
        gsap.set(textRef.value, { x: -12, color: "#ffffff" });
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ onClick: (__VLS_ctx.toggleTheme) },
    ...{ class: "theme-toggle" },
    ref: "toggleRef",
});
/** @type {typeof __VLS_ctx.toggleRef} */ ;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toggle-bg" },
    ref: "bgRef",
});
/** @type {typeof __VLS_ctx.bgRef} */ ;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toggle-text" },
    ref: "textRef",
});
/** @type {typeof __VLS_ctx.textRef} */ ;
(__VLS_ctx.isDark ? "深色模式" : "浅色模式");
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toggle-handle-container" },
    ref: "handleWrapperRef",
});
/** @type {typeof __VLS_ctx.handleWrapperRef} */ ;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toggle-handle" },
    ref: "handleRef",
});
/** @type {typeof __VLS_ctx.handleRef} */ ;
/** @type {__VLS_StyleScopedClasses['theme-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-bg']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-text']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-handle-container']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-handle']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            isDark: isDark,
            toggleRef: toggleRef,
            bgRef: bgRef,
            textRef: textRef,
            handleWrapperRef: handleWrapperRef,
            handleRef: handleRef,
            toggleTheme: toggleTheme,
        };
    },
    emits: {},
    props: {
        modelValue: {
            type: Boolean,
            default: true
        }
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    emits: {},
    props: {
        modelValue: {
            type: Boolean,
            default: true
        }
    },
});
; /* PartiallyEnd: #4569/main.vue */
//# sourceMappingURL=ThemeToggle.vue.js.map