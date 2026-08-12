import express from 'express';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

app.get('/api/health', (_req, res) => {
	res.json({
		status: 'ok',
		service: 'ASOFT AI Services Web',
		product: 'ERPX',
	});
});

app.listen(PORT, () => {
	console.log(`ASOFT AI Services Web backend running on http://localhost:${PORT}`);
});
