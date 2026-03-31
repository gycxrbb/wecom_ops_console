import { ref, onMounted, reactive } from 'vue';
import request from '@/utils/request';
import { ElMessage } from 'element-plus';
const groups = ref([]);
const templates = ref([]);
const selectedTemplate = ref(null);
const previewResult = ref('暂无预览');
const form = reactive({
    groups: [],
    msg_type: 'text',
    content: '',
    variables: '{}',
    template_id: null
});
const scheduleForm = reactive({
    title: '',
    schedule_type: 'once',
    run_at: '',
    cron_expr: ''
});
const fetchBaseData = async () => {
    try {
        const res1 = await request.get('/v1/groups');
        const res2 = await request.get('/v1/templates');
        groups.value = res1.list || res1;
        templates.value = res2.list || res2;
    }
    catch (e) {
        console.error(e);
    }
};
const handleTemplateChange = (val) => {
    const t = templates.value.find(x => x.id === val);
    if (t) {
        form.content = t.content;
        form.msg_type = t.msg_type;
        form.variables = t.variables_schema || '{}';
        form.template_id = t.id;
    }
    else {
        form.template_id = null;
    }
};
const handlePreview = async () => {
    try {
        const res = await request.post('/v1/preview', {
            template_id: form.template_id,
            content: form.content,
            variables: JSON.parse(form.variables || '{}')
        });
        previewResult.value = JSON.stringify(res, null, 2);
    }
    catch (e) {
        previewResult.value = '预览失败: ' + String(e);
    }
};
const handleSend = async () => {
    if (form.groups.length === 0) {
        return ElMessage.warning('请选择群组');
    }
    try {
        await request.post('/v1/send', {
            group_ids: form.groups,
            msg_type: form.msg_type,
            content: form.content,
            variables: JSON.parse(form.variables || '{}')
        });
        ElMessage.success('已触发发送任务');
    }
    catch (e) {
        console.error(e);
    }
};
const handleSchedule = async () => {
    if (form.groups.length === 0) {
        return ElMessage.warning('请选择群组');
    }
    try {
        await request.post('/v1/schedules', {
            title: scheduleForm.title,
            group_ids: form.groups.join(','),
            schedule_type: scheduleForm.schedule_type,
            run_at: scheduleForm.run_at || null,
            cron_expr: scheduleForm.cron_expr || null,
            msg_type: form.msg_type,
            content: form.content,
            variables: form.variables
        });
        ElMessage.success('定时任务创建成功');
    }
    catch (e) {
        console.error(e);
    }
};
onMounted(() => {
    fetchBaseData();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "view-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
const __VLS_0 = {}.ElRow;
/** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    gutter: (20),
}));
const __VLS_2 = __VLS_1({
    gutter: (20),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    span: (12),
}));
const __VLS_6 = __VLS_5({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.ElCard;
/** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
{
    const { header: __VLS_thisSlot } = __VLS_11.slots;
}
const __VLS_12 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    labelWidth: "100px",
}));
const __VLS_14 = __VLS_13({
    labelWidth: "100px",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    label: "群组",
}));
const __VLS_18 = __VLS_17({
    label: "群组",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
const __VLS_20 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.form.groups),
    multiple: true,
    placeholder: "选择群组",
    ...{ style: {} },
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.form.groups),
    multiple: true,
    placeholder: "选择群组",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
for (const [g] of __VLS_getVForSourceType((__VLS_ctx.groups))) {
    const __VLS_24 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        key: (g.id),
        label: (g.name),
        value: (g.id),
    }));
    const __VLS_26 = __VLS_25({
        key: (g.id),
        label: (g.name),
        value: (g.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
}
var __VLS_23;
var __VLS_19;
const __VLS_28 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    label: "模板",
}));
const __VLS_30 = __VLS_29({
    label: "模板",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.selectedTemplate),
    placeholder: "使用模板",
    clearable: true,
    ...{ style: {} },
}));
const __VLS_34 = __VLS_33({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.selectedTemplate),
    placeholder: "使用模板",
    clearable: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_36;
let __VLS_37;
let __VLS_38;
const __VLS_39 = {
    onChange: (__VLS_ctx.handleTemplateChange)
};
__VLS_35.slots.default;
for (const [t] of __VLS_getVForSourceType((__VLS_ctx.templates))) {
    const __VLS_40 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        key: (t.id),
        label: (t.name),
        value: (t.id),
    }));
    const __VLS_42 = __VLS_41({
        key: (t.id),
        label: (t.name),
        value: (t.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
}
var __VLS_35;
var __VLS_31;
const __VLS_44 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    label: "消息类型",
}));
const __VLS_46 = __VLS_45({
    label: "消息类型",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
const __VLS_48 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    modelValue: (__VLS_ctx.form.msg_type),
    ...{ style: {} },
}));
const __VLS_50 = __VLS_49({
    modelValue: (__VLS_ctx.form.msg_type),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
const __VLS_52 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    label: "文本",
    value: "text",
}));
const __VLS_54 = __VLS_53({
    label: "文本",
    value: "text",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
const __VLS_56 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    label: "Markdown",
    value: "markdown",
}));
const __VLS_58 = __VLS_57({
    label: "Markdown",
    value: "markdown",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
const __VLS_60 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    label: "图片",
    value: "image",
}));
const __VLS_62 = __VLS_61({
    label: "图片",
    value: "image",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
const __VLS_64 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    label: "图文 (News)",
    value: "news",
}));
const __VLS_66 = __VLS_65({
    label: "图文 (News)",
    value: "news",
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
const __VLS_68 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    label: "文件",
    value: "file",
}));
const __VLS_70 = __VLS_69({
    label: "文件",
    value: "file",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
const __VLS_72 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    label: "模板卡片",
    value: "template_card",
}));
const __VLS_74 = __VLS_73({
    label: "模板卡片",
    value: "template_card",
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
var __VLS_51;
var __VLS_47;
if (__VLS_ctx.selectedTemplate) {
    const __VLS_76 = {}.ElFormItem;
    /** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        label: "变量(JSON)",
    }));
    const __VLS_78 = __VLS_77({
        label: "变量(JSON)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    const __VLS_80 = {}.ElInput;
    /** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        type: "textarea",
        rows: (4),
        modelValue: (__VLS_ctx.form.variables),
    }));
    const __VLS_82 = __VLS_81({
        type: "textarea",
        rows: (4),
        modelValue: (__VLS_ctx.form.variables),
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    var __VLS_79;
}
const __VLS_84 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    label: "内容",
}));
const __VLS_86 = __VLS_85({
    label: "内容",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
const __VLS_88 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    type: "textarea",
    rows: (6),
    modelValue: (__VLS_ctx.form.content),
}));
const __VLS_90 = __VLS_89({
    type: "textarea",
    rows: (6),
    modelValue: (__VLS_ctx.form.content),
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
var __VLS_87;
const __VLS_92 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({}));
const __VLS_94 = __VLS_93({}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
const __VLS_96 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    ...{ 'onClick': {} },
    type: "info",
}));
const __VLS_98 = __VLS_97({
    ...{ 'onClick': {} },
    type: "info",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
let __VLS_100;
let __VLS_101;
let __VLS_102;
const __VLS_103 = {
    onClick: (__VLS_ctx.handlePreview)
};
__VLS_99.slots.default;
var __VLS_99;
const __VLS_104 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_106 = __VLS_105({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
let __VLS_108;
let __VLS_109;
let __VLS_110;
const __VLS_111 = {
    onClick: (__VLS_ctx.handleSend)
};
__VLS_107.slots.default;
var __VLS_107;
var __VLS_95;
var __VLS_15;
var __VLS_11;
var __VLS_7;
const __VLS_112 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    span: (12),
}));
const __VLS_114 = __VLS_113({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
__VLS_115.slots.default;
const __VLS_116 = {}.ElCard;
/** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    ...{ style: {} },
}));
const __VLS_118 = __VLS_117({
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
__VLS_119.slots.default;
{
    const { header: __VLS_thisSlot } = __VLS_119.slots;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
    ...{ class: "preview-box" },
});
(__VLS_ctx.previewResult);
var __VLS_119;
const __VLS_120 = {}.ElCard;
/** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
// @ts-ignore
const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({}));
const __VLS_122 = __VLS_121({}, ...__VLS_functionalComponentArgsRest(__VLS_121));
__VLS_123.slots.default;
{
    const { header: __VLS_thisSlot } = __VLS_123.slots;
}
const __VLS_124 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
    labelWidth: "100px",
}));
const __VLS_126 = __VLS_125({
    labelWidth: "100px",
}, ...__VLS_functionalComponentArgsRest(__VLS_125));
__VLS_127.slots.default;
const __VLS_128 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    label: "任务标题",
}));
const __VLS_130 = __VLS_129({
    label: "任务标题",
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
__VLS_131.slots.default;
const __VLS_132 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
    modelValue: (__VLS_ctx.scheduleForm.title),
}));
const __VLS_134 = __VLS_133({
    modelValue: (__VLS_ctx.scheduleForm.title),
}, ...__VLS_functionalComponentArgsRest(__VLS_133));
var __VLS_131;
const __VLS_136 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
    label: "任务类型",
}));
const __VLS_138 = __VLS_137({
    label: "任务类型",
}, ...__VLS_functionalComponentArgsRest(__VLS_137));
__VLS_139.slots.default;
const __VLS_140 = {}.ElRadioGroup;
/** @type {[typeof __VLS_components.ElRadioGroup, typeof __VLS_components.elRadioGroup, typeof __VLS_components.ElRadioGroup, typeof __VLS_components.elRadioGroup, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    modelValue: (__VLS_ctx.scheduleForm.schedule_type),
}));
const __VLS_142 = __VLS_141({
    modelValue: (__VLS_ctx.scheduleForm.schedule_type),
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
__VLS_143.slots.default;
const __VLS_144 = {}.ElRadio;
/** @type {[typeof __VLS_components.ElRadio, typeof __VLS_components.elRadio, typeof __VLS_components.ElRadio, typeof __VLS_components.elRadio, ]} */ ;
// @ts-ignore
const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
    label: "once",
}));
const __VLS_146 = __VLS_145({
    label: "once",
}, ...__VLS_functionalComponentArgsRest(__VLS_145));
__VLS_147.slots.default;
var __VLS_147;
const __VLS_148 = {}.ElRadio;
/** @type {[typeof __VLS_components.ElRadio, typeof __VLS_components.elRadio, typeof __VLS_components.ElRadio, typeof __VLS_components.elRadio, ]} */ ;
// @ts-ignore
const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
    label: "cron",
}));
const __VLS_150 = __VLS_149({
    label: "cron",
}, ...__VLS_functionalComponentArgsRest(__VLS_149));
__VLS_151.slots.default;
var __VLS_151;
var __VLS_143;
var __VLS_139;
if (__VLS_ctx.scheduleForm.schedule_type === 'once') {
    const __VLS_152 = {}.ElFormItem;
    /** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
        label: "执行时间",
    }));
    const __VLS_154 = __VLS_153({
        label: "执行时间",
    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
    __VLS_155.slots.default;
    const __VLS_156 = {}.ElDatePicker;
    /** @type {[typeof __VLS_components.ElDatePicker, typeof __VLS_components.elDatePicker, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        modelValue: (__VLS_ctx.scheduleForm.run_at),
        type: "datetime",
        placeholder: "选择时间",
        valueFormat: "YYYY-MM-DDTHH:mm:ss",
    }));
    const __VLS_158 = __VLS_157({
        modelValue: (__VLS_ctx.scheduleForm.run_at),
        type: "datetime",
        placeholder: "选择时间",
        valueFormat: "YYYY-MM-DDTHH:mm:ss",
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    var __VLS_155;
}
if (__VLS_ctx.scheduleForm.schedule_type === 'cron') {
    const __VLS_160 = {}.ElFormItem;
    /** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        label: "Cron表达式",
    }));
    const __VLS_162 = __VLS_161({
        label: "Cron表达式",
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    __VLS_163.slots.default;
    const __VLS_164 = {}.ElInput;
    /** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        modelValue: (__VLS_ctx.scheduleForm.cron_expr),
        placeholder: "* * * * *",
    }));
    const __VLS_166 = __VLS_165({
        modelValue: (__VLS_ctx.scheduleForm.cron_expr),
        placeholder: "* * * * *",
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    var __VLS_163;
}
const __VLS_168 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({}));
const __VLS_170 = __VLS_169({}, ...__VLS_functionalComponentArgsRest(__VLS_169));
__VLS_171.slots.default;
const __VLS_172 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    ...{ 'onClick': {} },
    type: "success",
}));
const __VLS_174 = __VLS_173({
    ...{ 'onClick': {} },
    type: "success",
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
let __VLS_176;
let __VLS_177;
let __VLS_178;
const __VLS_179 = {
    onClick: (__VLS_ctx.handleSchedule)
};
__VLS_175.slots.default;
var __VLS_175;
var __VLS_171;
var __VLS_127;
var __VLS_123;
var __VLS_115;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['view-container']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-box']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            groups: groups,
            templates: templates,
            selectedTemplate: selectedTemplate,
            previewResult: previewResult,
            form: form,
            scheduleForm: scheduleForm,
            handleTemplateChange: handleTemplateChange,
            handlePreview: handlePreview,
            handleSend: handleSend,
            handleSchedule: handleSchedule,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
//# sourceMappingURL=SendCenter.vue.js.map