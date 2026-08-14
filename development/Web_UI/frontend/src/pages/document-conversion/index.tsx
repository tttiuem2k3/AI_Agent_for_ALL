import {
	AlertTriangle,
	Copy,
	Download,
	FileText,
	FileUp,
	RefreshCw,
	RotateCcw,
	Trash2,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { toast } from 'sonner';

import { documentConversionApi } from '@/api';
import type { DocumentConversionHealth, DocumentConversionResult } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const MAX_FILE_BYTES = 50 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [
	'.doc',
	'.docx',
	'.odt',
	'.pdf',
	'.ppt',
	'.pptx',
	'.rtf',
	'.epub',
	'.xls',
	'.xlsx',
	'.ods',
	'.odp',
	'.csv',
];

const FORMAT_GROUPS = [
	['DOC / DOCX', 'Word → Markdown'],
	['XLS / XLSX / ODS', 'Spreadsheet → Markdown'],
	['PPT / PPTX / ODP', 'Presentation → Markdown'],
	['PDF', 'PDF → Markdown'],
	['CSV / RTF / EPUB / ODT', 'Other documents → Markdown'],
] as const;

function formatBytes(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function extensionOf(name: string): string {
	const dot = name.lastIndexOf('.');
	return dot >= 0 ? name.slice(dot).toLowerCase() : '';
}

export function DocumentConversionPage() {
	const inputRef = useRef<HTMLInputElement>(null);
	const [health, setHealth] = useState<DocumentConversionHealth | null>(null);
	const [file, setFile] = useState<File | null>(null);
	const [result, setResult] = useState<DocumentConversionResult | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [converting, setConverting] = useState(false);
	const [dragging, setDragging] = useState(false);

	const refreshHealth = async () => {
		try {
			setHealth(await documentConversionApi.health());
		} catch (healthError) {
			setHealth({
				ok: false,
				message: healthError instanceof Error ? healthError.message : String(healthError),
			});
		}
	};

	useEffect(() => {
		void refreshHealth();
	}, []);

	const fileValid = useMemo(() => {
		if (!file) return false;
		return ACCEPTED_EXTENSIONS.includes(extensionOf(file.name)) && file.size <= MAX_FILE_BYTES;
	}, [file]);

	const chooseFile = (candidate: File | null) => {
		setResult(null);
		setError(null);
		if (!candidate) {
			setFile(null);
			return;
		}
		const extension = extensionOf(candidate.name);
		if (!ACCEPTED_EXTENSIONS.includes(extension)) {
			setFile(null);
			setError(`Định dạng ${extension || '(không có phần mở rộng)'} chưa được hỗ trợ.`);
			return;
		}
		if (candidate.size > MAX_FILE_BYTES) {
			setFile(null);
			setError('File vượt quá giới hạn 50 MB của màn hình test.');
			return;
		}
		setFile(candidate);
	};

	const clearFileInput = () => {
		if (inputRef.current) inputRef.current.value = '';
	};

	const removeFile = () => {
		if (converting) return;
		setFile(null);
		setError(null);
		setDragging(false);
		clearFileInput();
	};

	const resetAll = () => {
		if (converting) return;
		setFile(null);
		setResult(null);
		setError(null);
		setDragging(false);
		clearFileInput();
	};

	const convert = async () => {
		if (!file || !fileValid) return;
		setConverting(true);
		setError(null);
		setResult(null);
		try {
			setResult(await documentConversionApi.convert(file));
		} catch (conversionError) {
			setError(
				conversionError instanceof Error
					? conversionError.message
					: String(conversionError),
			);
		} finally {
			setConverting(false);
		}
	};

	const copyMarkdown = async () => {
		if (!result) return;
		await navigator.clipboard.writeText(result.markdown);
		toast.success('Đã sao chép Markdown');
	};

	const downloadMarkdown = () => {
		if (!result) return;
		const blob = new Blob([result.markdown], { type: 'text/markdown;charset=utf-8' });
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement('a');
		anchor.href = url;
		anchor.download = result.filename.replace(/\.[^.]+$/, '') + '.md';
		anchor.click();
		URL.revokeObjectURL(url);
	};

	return (
		<div className="flex h-full w-full flex-col overflow-hidden bg-sidebar">
			<header className="flex items-start justify-between gap-4 p-5">
				<div>
					<h1 className="text-2xl font-semibold">Document Conversion</h1>
					<p className="mt-1 text-sm text-muted-foreground">
						Chuyển đổi file tài liệu sang Markdown.
					</p>
				</div>
			</header>

			<main className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-auto rounded-t-3xl bg-background p-5 xl:grid-cols-[380px_minmax(0,1fr)] xl:overflow-hidden">
				<section className="flex min-w-0 flex-col gap-3 self-start xl:h-full xl:min-h-0 xl:self-stretch xl:overflow-hidden">
					<Card className="shrink-0">
						<CardHeader className="grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
							<CardTitle className="min-w-0 text-base">
								1. Chọn file cần chuyển đổi
							</CardTitle>
							<Button
								size="icon-sm"
								variant="outline"
								disabled={converting || (!file && !result && !error)}
								onClick={resetAll}
								tooltip="Reset"
								aria-label="Reset"
							>
								<RotateCcw className="size-3.5" />
							</Button>
						</CardHeader>
						<CardContent className="space-y-4">
							<input
								ref={inputRef}
								type="file"
								className="hidden"
								accept={ACCEPTED_EXTENSIONS.join(',')}
								onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
							/>

							<div
								className={`flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
									dragging
										? 'border-primary bg-primary/5'
										: 'border-border hover:bg-muted/40'
								}`}
								onClick={() => inputRef.current?.click()}
								onDragEnter={(event) => {
									event.preventDefault();
									setDragging(true);
								}}
								onDragOver={(event) => event.preventDefault()}
								onDragLeave={() => setDragging(false)}
								onDrop={(event) => {
									event.preventDefault();
									setDragging(false);
									chooseFile(event.dataTransfer.files?.[0] ?? null);
								}}
							>
								<FileUp className="mb-3 size-9 text-muted-foreground" />
								<div className="font-medium">Kéo thả file vào đây</div>
								<div className="mt-1 text-sm text-muted-foreground">
									hoặc nhấn để chọn file · tối đa 50 MB
								</div>
							</div>

							{file && (
								<div className="flex items-center justify-between rounded-lg border bg-muted/30 p-3">
									<div className="min-w-0">
										<div className="truncate text-sm font-medium">
											{file.name}
										</div>
										<div className="text-xs text-muted-foreground">
											{formatBytes(file.size)}
										</div>
									</div>
									<div className="flex shrink-0 items-center gap-2">
										<Badge variant="outline">
											{extensionOf(file.name).slice(1).toUpperCase()}
										</Badge>
										<Button
											size="icon-sm"
											variant="outline"
											disabled={converting}
											onClick={removeFile}
											tooltip="Xóa file"
											aria-label="Xóa file"
										>
											<Trash2 className="size-3.5" />
										</Button>
									</div>
								</div>
							)}

							{error && (
								<div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
									{error}
								</div>
							)}
						</CardContent>
						<CardFooter className="mt-1">
							<Button
								className="h-10 w-full text-sm font-semibold"
								disabled={!fileValid || converting || health?.ok !== true}
								onClick={() => void convert()}
							>
								{converting ? <RefreshCw className="animate-spin" /> : <FileText />}
								{converting
									? 'Đang chuyển đổi...'
									: health?.ok !== true
										? 'Service chưa sẵn sàng'
										: fileValid
											? 'Chuyển sang Markdown'
											: 'Chọn file để chuyển đổi'}
							</Button>
						</CardFooter>
					</Card>

					<Card size="sm" className="shrink-0">
						<CardHeader>
							<CardTitle className="text-sm">Định dạng hỗ trợ</CardTitle>
						</CardHeader>
						<CardContent className="flex flex-wrap gap-1.5">
							{FORMAT_GROUPS.map(([formats]) => (
								<Badge
									key={formats}
									variant="outline"
									className="px-2 py-1 text-xs font-medium"
								>
									{formats}
								</Badge>
							))}
						</CardContent>
					</Card>
				</section>

				<section className="min-h-[520px] min-w-0 xl:h-full xl:min-h-0">
					<Card className="flex h-full min-h-[520px] flex-col xl:min-h-0">
						<CardHeader className="flex-row items-center justify-between gap-3">
							<div>
								<CardTitle className="text-base">2. Kết quả Markdown</CardTitle>
								{result && (
									<div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
										<span>Format: {result.format}</span>
										<span>·</span>
										<span>{result.elapsed_ms} ms</span>
										<span>·</span>
										<span>{result.markdown_chars.toLocaleString()} ký tự</span>
									</div>
								)}
							</div>

							{result && (
								<div className="flex gap-2">
									<Button
										size="sm"
										variant="outline"
										onClick={() => void copyMarkdown()}
									>
										<Copy /> Sao chép
									</Button>
									<Button size="sm" variant="outline" onClick={downloadMarkdown}>
										<Download /> Tải .md
									</Button>
								</div>
							)}
						</CardHeader>

						<CardContent className="min-h-0 flex-1 overflow-hidden">
							{!result ? (
								<div className="flex h-full min-h-96 flex-col items-center justify-center text-center text-muted-foreground">
									<FileText className="mb-3 size-10" />
									<div className="font-medium text-foreground">
										Chưa có kết quả
									</div>
									<div className="mt-1 max-w-md text-sm">
										Chọn một file ở cột bên trái và chạy chuyển đổi để xem
										Markdown thực tế.
									</div>
								</div>
							) : (
								<Tabs
									defaultValue="preview"
									className="flex h-full min-h-0 flex-col"
								>
									<TabsList className="w-fit">
										<TabsTrigger value="preview">Preview</TabsTrigger>
										<TabsTrigger value="raw">Markdown thô</TabsTrigger>
									</TabsList>

									{result.warnings.length > 0 && (
										<div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
											<div className="mb-1 flex items-center gap-2 font-medium">
												<AlertTriangle className="size-4" /> Warning
											</div>
											{result.warnings.join(', ')}
										</div>
									)}

									<TabsContent
										value="preview"
										className="mt-3 min-h-0 flex-1 overflow-auto rounded-lg border p-5"
									>
										<div className="prose prose-sm max-w-none dark:prose-invert">
											<ReactMarkdown remarkPlugins={[remarkGfm]}>
												{result.markdown}
											</ReactMarkdown>
										</div>
									</TabsContent>

									<TabsContent
										value="raw"
										className="mt-3 min-h-0 flex-1 overflow-auto rounded-lg border bg-muted/20 p-4"
									>
										<pre className="whitespace-pre-wrap break-words font-mono text-xs leading-5 text-foreground">
											{result.markdown}
										</pre>
									</TabsContent>
								</Tabs>
							)}
						</CardContent>
					</Card>
				</section>
			</main>
		</div>
	);
}
